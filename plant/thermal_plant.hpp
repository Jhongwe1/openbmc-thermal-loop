// SPDX-License-Identifier: Apache-2.0
//
// 單節點伺服器熱系統的集總參數模型。
//
// ⚠️ D4 版：只有骨架，物理還沒進來（W3 D5~D6 才寫）。
//    今天這個檔案存在的唯一目的，是讓建置鏈路可以先立起來並且是綠的。
#pragma once

namespace thermal
{

/** 熱模型的參數。每一個值的物理理由寫在 docs/plant-model.md（W3 D5）。 */
struct PlantParams
{
    /** 機房進風溫度（°C）。 */
    double tAmb = 25.0;
};

} // namespace thermal
