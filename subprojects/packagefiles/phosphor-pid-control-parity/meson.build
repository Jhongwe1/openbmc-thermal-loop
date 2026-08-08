# 這份 meson.build 會蓋掉上游 phosphor-pid-control 自己的那一份
# （meson wrap 的 patch_directory 機制）。
#
# ★ 為什麼要蓋掉
#   上游那份會建整個 swampd，需要 sdbusplus、phosphor-logging、boost、systemd…
#   而我只要一個函式：ec::pid()。把整包建起來只為了比對一個函式，
#   會讓「別人 clone 下來跑一次」變成一件很難的事。
#
# ★ 為什麼不是把檔案複製進我的 repo（計畫的止損方案）
#   複製進來的話，「我的測試真的在編上游的程式碼」就退化成
#   「我的測試在編一份我自己維護的副本」。釘住 commit ＋ 由 meson 去抓，
#   讓那句話仍然成立，而且抓的是哪一版寫在 .wrap 裡，任何人都查得到。
#
# ★ 為什麼 warning_level=0 / werror=false
#   我的主專案是 warning_level=3 + werror=true。把別人的原始碼硬塞進我的旗標下，
#   為了編過去而修改它，等於比對的已經不是上游那一份了。
project(
    'phosphor-pid-control-ec-pid',
    'cpp',
    version: '0.1.0',
    license: 'Apache-2.0',
    default_options: ['cpp_std=c++20', 'warning_level=0', 'werror=false'],
    meson_version: '>=1.1',
)

# pid.cpp 呼叫 LogInit / LogPeek / LogTimestamp / LogContext（在 pid/ec/logging.cpp），
# logging.cpp 又用到 coreLoggingEnabled / loggingPath 等全域旗標（在 pid/tuning.cpp）。
# 這三個編譯單元合起來只依賴標準函式庫 —— 這是實際試出來的，不是猜的。
ec_pid_inc = include_directories('.')

ec_pid_lib = static_library(
    'upstream_ec_pid',
    ['pid/ec/pid.cpp', 'pid/ec/logging.cpp', 'pid/tuning.cpp'],
    include_directories: ec_pid_inc,
)

upstream_ec_pid_dep = declare_dependency(
    link_with: ec_pid_lib,
    include_directories: ec_pid_inc,
)

meson.override_dependency('upstream-ec-pid', upstream_ec_pid_dep)
