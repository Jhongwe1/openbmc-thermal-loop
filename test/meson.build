test_deps = [plant_dep, gtest_dep]
if gmock_dep.found()
    test_deps += gmock_dep
endif

# protocol: 'gtest' 讓 meson 解析 gtest 的 XML 輸出，
# 於是 meson test 的報告是「幾個 test case」而不是「幾個執行檔」。
# 沒有它，兩個 case 全掛也只會顯示「1 個測試失敗」。
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
    )
else
    warning(
        'Python 測試被跳過：' + py.full_path() + ' 沒有 pytest 或 pandas。' +
        '先 `source ~/.venvs/thermal/bin/activate` 再 `meson setup --reconfigure build`。',
    )
endif
