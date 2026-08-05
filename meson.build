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
    ['plant/thermal_plant.cpp'],
    include_directories: inc,
)
plant_dep = declare_dependency(
    link_with: plant_lib,
    include_directories: inc,
)

# controller/ 在 W5 加入
# controller_lib = static_library('controller', ['controller/pi.cpp'], ...)

# ── 手動驗收工具（W3 D6）──────────────────────────────────────────────
# 不是測試，是「用眼睛看曲線合不合物理直覺」用的。測試在 test/。
executable('plant_probe', 'bench/plant_probe.cpp', dependencies: [plant_dep])

# ── L1 模擬執行檔（吐 CSV 給 bench/ 用）────────────────────────────────
# executable('sim', 'bench/sim.cpp', dependencies: [plant_dep])   # W5 啟用

# ── L0 測試 ────────────────────────────────────────────────────────────
if get_option('tests').allowed()
    subdir('test')
endif
