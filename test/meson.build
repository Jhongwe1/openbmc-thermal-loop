test_deps = [plant_dep, gtest_dep]
if gmock_dep.found()
    test_deps += gmock_dep
endif

# protocol: 'gtest' 讓 meson 用 --gtest_output=xml 跑，並解析那份 XML。
#
# ⚠️ **它不會改變主控台摘要的數字。** `Ok: 6` 數的仍然是 test() 項目
#    （5 支 gtest 執行檔 + 1 個 pytest），不是 case。
#    真正的差別在 `build/meson-logs/testlog.junit.xml`：
#    有它的時候裡面是 **33 個 <testcase>**（每個 gtest case 一筆），
#    沒有它就只有 6 筆「整支執行檔過/不過」。
#
#    要看 case 數就問執行檔自己：`./build/test/test_plant --gtest_list_tests`。
#
#    為什麼還是要開：CI（W10）吃的是那份 JUnit XML。
#    「哪一個 case 紅了」與「哪一支執行檔紅了」在報告上差很多，
#    而且 case 級的結果才看得出「同一支裡有幾條同時壞掉」。
test(
    'plant',
    executable('test_plant', 'test_plant.cpp', dependencies: test_deps),
    protocol: 'gtest',
)

test(
    'identify',
    executable('test_identify', 'test_identify.cpp', dependencies: test_deps),
    protocol: 'gtest',
)

test(
    'pi',
    executable(
        'test_pi',
        'test_pi.cpp',
        dependencies: test_deps + [controller_dep],
    ),
    protocol: 'gtest',
)

# ★ 閉環：把 controller 與 plant 接起來。
#   parity 測試證明的是「算術跟上游一樣」，那不等於「這是個能收斂的控制器」——
#   兩個實作可以逐位元一致地一起錯。這一支補的是那個缺口。
test(
    'closed_loop',
    executable(
        'test_closed_loop',
        'test_closed_loop.cpp',
        dependencies: test_deps + [controller_dep],
    ),
    protocol: 'gtest',
)

# upstream_pid_dep 在沒有 subproject 時是 disabler()，整個 target 會被跳過，
# 其他測試照常建置。這正是 disabler 的用途：缺一個可選相依不該讓 build 死掉。
test(
    'parity_upstream',
    executable(
        'test_parity_upstream',
        'test_parity_upstream.cpp',
        dependencies: test_deps + [controller_dep, upstream_pid_dep],
    ),
    protocol: 'gtest',
)

# ── Python 這一側（bench/metrics.py 與注入路徑預測式）────────────────────
#
# ★ 為什麼接進 meson test，而不是另外做一套跑法
#   兩套 test runner 的結果是**大家只會記得跑其中一套**。
#   `meson test -C build` 必須是「跑完所有測試」的那一個指令。
#
# ⚠️ 這裡有一個會安靜咬人的地方（坑 27 的 Python 版）：
#    `find_installation('python3')` 是在 **configure 時**沿 PATH 找的，
#    找到什麼就**寫死在 build 目錄裡**。這台機器上：
#      · 系統的 /usr/bin/python3   —— 沒有 pandas、沒有 pytest
#      · ~/.venvs/thermal 的 python3 —— 兩個都有
#    所以**沒有先 activate venv 就 meson setup 的話，這個測試會消失**，
#    而 `meson test` 依然全綠。
#
#    對策有兩層：
#      1. 這裡用 warning() 而不是 message()，meson 會把它列在 configure
#         結尾的警告區塊，看得到。
#      2. tools/mutation_check.sh 的 EXPECTED_TESTS 列了 'metrics'，
#         測試不見時它會**拒絕執行**並說明原因，而不是回報一堆假的 survivor。
py = import('python').find_installation('python3', required: false)

python_tests_ok = false
if py.found()
    have_pytest = run_command(py, '-c', 'import pytest', check: false)
    have_pandas = run_command(py, '-c', 'import pandas', check: false)
    python_tests_ok = (
        have_pytest.returncode() == 0 and have_pandas.returncode() == 0
    )
endif

if python_tests_ok
    test(
        'metrics',
        py,
        args: [
            '-m', 'pytest', '-q',
            meson.current_source_dir() / 'python',
        ],
        # metrics.py 與 exp04 的 CSV 都是相對 repo 根目錄引用的。
        workdir: meson.project_source_root(),
        # ⚠️ meson 預設每個測試 30 秒。figures 的迴歸測試對**每張圖**都要
        #    重畫三次（與 repo 比對一次 + 決定性檢查兩次），W7 加入 Fig 3 後
        #    整包剛好超過 30 秒（實測 31.25s 被 SIGTERM）——症狀是 TIMEOUT，
        #    看起來像測試壞了，其實只是圖變多了。
        timeout: 300,
        # ★ test_sim_cli 用子行程跑 build/sim —— 要在這裡宣告，
        #   `meson test` 才會先把它建出來。本機看不出少了這行
        #   （build/ 裡總是有跑過 meson compile 的殘留），
        #   只有乾淨 clone 會倒：那正是乾淨 clone 檢查存在的理由。
        depends: sim_exe,
    )
else
    warning(
        'Python 測試被跳過：' + py.full_path() + ' 沒有 pytest 或 pandas。' +
        '先 `source ~/.venvs/thermal/bin/activate` 再 `meson setup --reconfigure build`。',
    )
endif
