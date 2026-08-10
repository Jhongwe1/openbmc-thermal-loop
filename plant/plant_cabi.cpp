// SPDX-License-Identifier: Apache-2.0
//
// plant 的 C ABI 薄封裝 —— 給 L2 的 Python 橋接（harness/dbus_bridge.py）用。
//
// 為什麼是 C ABI 而不是直接給 Python 綁 C++：
//   ctypes 只認 C 的符號名。C++ 的名字會被編譯器改編（mangling），
//   而 mangled name 隨編譯器/版本而變 —— 綁它等於把橋接綁在編譯器版本上。
//
// ★ 這一層**只做轉呼叫**，不做任何 IO、不含任何邏輯。
//   plant 的「step() 不做 IO」約束（見 thermal_plant.hpp）因此原封不動：
//   L0 gtest、L1 sim、L2 bridge 跑的是**同一份** plant 程式碼 ——
//   這正是「L1 與 L2 的圖可以直接疊」這個宣稱的前提。
#include "plant/thermal_plant.hpp"

extern "C"
{
    /// 建一個 plant。參數全部用預設值 —— 與 L1 sim 不帶覆寫旗標時相同。
    /// L2 刻意不開放覆寫參數：兩層的 plant 必須逐參數一致，疊圖才有意義。
    void* plant_create(double dt, unsigned seed)
    {
        return new thermal::ThermalPlant(thermal::PlantParams{}, dt, seed);
    }

    void plant_destroy(void* plant)
    {
        delete static_cast<thermal::ThermalPlant*>(plant);
    }

    /// 推進一步，回傳**感測器讀到的**溫度（含死區、遲滯、雜訊、量化）。
    /// L2 把它發佈到 D-Bus —— 與 BMC 上 hwmontempsensor 發佈的東西同級
    /// （那一側的量化由真的 tmp421 做，這一側由 plant 模型做）。
    double plant_step(void* plant, double pwm_pct, double power_w)
    {
        return static_cast<thermal::ThermalPlant*>(plant)->step(pwm_pct,
                                                                power_w);
    }

    /// 目前轉速 (RPM) —— 寫進假 tach 檔給 swampd 的 fan sensor 讀。
    double plant_rpm(void* plant)
    {
        return static_cast<thermal::ThermalPlant*>(plant)->rpm();
    }

    /// 模型內部真值 (°C)，只進 bridge 的 CSV 當證據，不進 D-Bus。
    double plant_die(void* plant)
    {
        return static_cast<thermal::ThermalPlant*>(plant)->dieTemp();
    }
}
