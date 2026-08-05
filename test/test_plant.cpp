// SPDX-License-Identifier: Apache-2.0
//
// D4 的測試只驗一件事：建置鏈路是通的。
// 真正的 L0 測試（SteadyState、MonotonicInPwm）在 W3 D7。
#include "plant/thermal_plant.hpp"

#include <gtest/gtest.h>

TEST(BuildSanity, DefaultAmbientIs25)
{
    const thermal::PlantParams p;
    EXPECT_DOUBLE_EQ(p.tAmb, 25.0);
}
