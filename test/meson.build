test_deps = [plant_dep, gtest_dep]
if gmock_dep.found()
    test_deps += gmock_dep
endif

test(
    'plant',
    executable('test_plant', 'test_plant.cpp', dependencies: test_deps),
)

# W5 加入：
# test('pi', executable('test_pi', 'test_pi.cpp', dependencies: test_deps))
# test(
#     'parity_upstream',
#     executable('test_parity_upstream', 'test_parity_upstream.cpp',
#                dependencies: test_deps + [upstream_pid_dep]),
# )
