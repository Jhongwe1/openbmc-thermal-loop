# 建置系統刻意與上游 phosphor-pid-control 一致：meson + ninja + gtest。
# 理由不是偏好，是 W5 的 parity 測試要把上游的 pid/ec/pid.cpp 直接拉進來編，
# 兩邊用同一套建置系統才有辦法在同一個編譯器、同一組旗標下逐步比對。
project(
    'openbmc-thermal-loop',
    'cpp',
    version: '0.1.0',
    license: 'Apache-2.0',
    default_options: [
        'cpp_std=c++20',
        'warning_level=3',
        # ★ werror 一開始會很煩，留著。上游也是這樣，而且它逼你把警告當錯誤處理。
        'werror=true',
    ],
    meson_version: '>=1.1',
)

# ── 相依 ───────────────────────────────────────────────────────────────
# 寫法沿用上游 phosphor-pid-control 的 test/meson.build：
# 先找系統的 gtest/gmock，找不到就退回 CMake subproject。
# disabler: true 的意思是「找不到的話，用到它的 target 自動被停用」，
# 而不是整個 configure 失敗 —— 這樣沒裝 gtest 的人仍然編得出程式庫。
gtest_dep = dependency('gtest', main: true, disabler: true, required: false)
gmock_dep = dependency('gmock', disabler: true, required: false)
if not gtest_dep.found() or not gmock_dep.found()
    gtest_proj = import('cmake').subproject('googletest', required: false)
    if gtest_proj.found()
        gtest_dep = declare_dependency(
            dependencies: [
                dependency('threads'),
                gtest_proj.dependency('gtest'),
                gtest_proj.dependency('gtest_main'),
            ],
        )
        gmock_dep = gtest_proj.dependency('gmock')
    else
        assert(not get_option('tests').enabled(), 'gtest 找不到，而且測試是必要的')
    endif
endif

# ── 我的程式庫 ─────────────────────────────────────────────────────────
# include_directories('.') 讓標頭檔一律寫成 "plant/thermal_plant.hpp"，
# 也就是「從 repo 根目錄看下去」的路徑。相對路徑（"../plant/..."）在測試檔裡
# 會隨檔案位置改變，是之後搬檔案時最常見的破壞來源。
inc = include_directories('.')

plant_lib = static_library(
    'plant',
    ['plant/thermal_plant.cpp', 'plant/identify.cpp'],
    include_directories: inc,
)
plant_dep = declare_dependency(
    link_with: plant_lib,
    include_directories: inc,
)

controller_lib = static_library(
    'controller',
    ['controller/pi.cpp'],
    include_directories: inc,
)
controller_dep = declare_dependency(
    link_with: controller_lib,
    include_directories: inc,
)

# ── 上游 ec::pid()：只為 parity 測試而編 ──────────────────────────────
#
# 只取 pid/ec/pid.cpp 這一個編譯單元，不是整包 phosphor-pid-control ——
# 整包會把 sdbusplus、systemd、boost 全部拖進來，而我要比對的只有一個函式。
#
# 為什麼不用 subproject()：上游的 meson.build 沒有 export 我需要的變數，
# 而且它自己的 dependency 一長串。直接把那個 .cpp 當成一份 source 加進測試的
# target，是本計畫建議的、也是實測可行的做法。
#
# ⚠️ pid.cpp 會 #include "logging.hpp"，那支又需要 nlohmann/json。
#    實際試出來的相依請見 test/meson.build 的註解。
# subprojects/phosphor-pid-control.wrap 釘住這台 BMC 上跑的那個 commit，
# 並用 patch_directory 換上一份只編 ec::pid() 所需三個編譯單元的 meson.build。
#
# ⚠️ 不要改成「直接把 subprojects/.../pid/ec/pid.cpp 加進我的 target」——
#    meson 會擋下來（Sandbox violation: Tried to grab file from a nested
#    subproject）。那是刻意的規則，不是 bug。
#
# disabler 的效果：沒抓 subproject 的人，parity 那個 target 自動被跳過，
# 其他測試照常建置。value=auto 時不會讓 configure 失敗。
#
# allow_fallback: true 是必要的。沒有它，required 為 false（也就是 auto）時
# meson 只會去找 pkg-config 與 cmake，**根本不會去看 wrap**，於是 parity 測試
# 會在沒有任何錯誤訊息的情況下靜靜消失。實測輸出是：
#     Run-time dependency upstream-ec-pid found: NO (tried pkgconfig and cmake)
# 「安靜地少建一個測試」比建置失敗危險得多 —— meson test 全綠，但綠的裡面
# 沒有它。
upstream_pid_dep = dependency(
    'upstream-ec-pid',
    required: get_option('upstream-parity'),
    allow_fallback: true,
    disabler: true,
)

# ── 手動驗收工具（W3 D6）──────────────────────────────────────────────
# 不是測試，是「用眼睛看曲線合不合物理直覺」用的。測試在 test/。
executable('plant_probe', 'bench/plant_probe.cpp', dependencies: [plant_dep])

# ── L1 模擬執行檔（吐 CSV 給 bench/ 用）────────────────────────────────
# stdout = CSV，stderr = 這次執行生效的完整參數。bench/exp01_sysid.py 兩個都收。
executable('sim', 'bench/sim.cpp', dependencies: [plant_dep, controller_dep])

# ── 分析工具：吃 CSV、吐 FOPDT 參數 ────────────────────────────────────
# 刻意與 sim 分開：sim 只產生資料，這支只消費資料。
# 合併的話很容易寫出「跑完順便擬合」的捷徑，那會讓「圖上的 tau 來自 repo 裡
# 那份 CSV」這個環節消失 —— 別人 clone 下來就只能相信我。
executable('identify_csv', 'bench/identify_csv.cpp', dependencies: [plant_dep])

# ── L0 測試 ────────────────────────────────────────────────────────────
if get_option('tests').allowed()
    subdir('test')
endif
