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

# W5 加入：
# test('pi', executable('test_pi', 'test_pi.cpp', dependencies: test_deps))
# test(
#     'parity_upstream',
#     executable('test_parity_upstream', 'test_parity_upstream.cpp',
#                dependencies: test_deps + [upstream_pid_dep]),
# )
