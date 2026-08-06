// SPDX-License-Identifier: Apache-2.0
//
// 從一份 CSV 算出 FOPDT 的 K / tau / theta / 殘差，印成 key=value。
//
//   ./build/identify_csv bench/data/exp01_sysid_seed0.csv --step-at 300 --du 20
//   k=-0.31...
//   tau=...
//   theta=...
//   residual_rms=...
//
// ★ 為什麼是「吃 CSV」而不是「自己再跑一次模擬」：
//   進 git 的那份 CSV 才是證據。擬合必須從**那份檔案**算出來，
//   而不是從一次新的模擬。否則「圖上的 tau」與「repo 裡的資料」
//   之間就少了一個可驗證的環節 —— 別人 clone 下來只能相信我。
//
// ★ 為什麼獨立成一支程式，而不是加一個 sim --identify 模式：
//   sim 的職責是**產生資料**，這支的職責是**分析資料**。
//   計畫建議合併（少一支程式），但那會讓 sim 同時能產生與消費資料，
//   之後很容易寫出「跑完順便擬合」的捷徑 —— 那正是上面那個環節消失的方式。
//   分開之後，唯一能餵給擬合的東西就是檔案。
//
// ★ 識別的邏輯只有一份（plant/identify.cpp），而且有 gtest 守著。
//   Python 那邊不重寫一次 —— 兩份實作遲早會不一致，而且不一致的時候
//   你不會知道哪一份是對的。
#include "plant/identify.hpp"

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

namespace
{

/** 在標頭列裡找欄位名的位置。找不到回傳 -1。 */
int columnIndex(const std::string& header, const std::string& want)
{
    std::stringstream ss(header);
    std::string cell;
    int i = 0;
    while (std::getline(ss, cell, ','))
    {
        if (cell == want)
        {
            return i;
        }
        ++i;
    }
    return -1;
}

/** 取一列的第 idx 欄。 */
double cellAt(const std::string& line, int idx)
{
    std::stringstream ss(line);
    std::string cell;
    for (int i = 0; std::getline(ss, cell, ','); ++i)
    {
        if (i == idx)
        {
            return std::strtod(cell.c_str(), nullptr);
        }
    }
    return 0.0;
}

} // namespace

int main(int argc, char** argv)
{
    const char* path = nullptr;
    double stepAt = -1.0;
    double du = 0.0;
    std::string yCol = "t_sense_c";

    for (int i = 1; i < argc; ++i)
    {
        const std::string k = argv[i];
        if (k.rfind("--", 0) != 0)
        {
            path = argv[i];
            continue;
        }
        if (i + 1 >= argc)
        {
            std::fprintf(stderr, "option %s 少了值\n", argv[i]);
            return 2;
        }
        const char* v = argv[++i];
        if (k == "--step-at")    stepAt = std::strtod(v, nullptr);
        else if (k == "--du")    du = std::strtod(v, nullptr);
        else if (k == "--column") yCol = v;
        else
        {
            std::fprintf(stderr, "unknown option: %s\n", k.c_str());
            return 2;
        }
    }

    if (path == nullptr || stepAt < 0.0 || du == 0.0)
    {
        std::fprintf(stderr,
                     "usage: identify_csv <csv> --step-at <s> --du <delta>"
                     " [--column t_sense_c]\n");
        return 2;
    }

    std::ifstream in(path);
    if (!in)
    {
        std::fprintf(stderr, "開不了 %s\n", path);
        return 1;
    }

    std::string header;
    if (!std::getline(in, header))
    {
        std::fprintf(stderr, "%s 是空的\n", path);
        return 1;
    }

    // ★ 依欄位**名字**找位置，不寫死欄號。CSV 加一欄就整批分析失效，
    //   而且失效的方式是「算出一個看起來很正常的錯數字」。
    const int iT = columnIndex(header, "t_s");
    const int iY = columnIndex(header, yCol);
    if (iT < 0 || iY < 0)
    {
        std::fprintf(stderr, "找不到欄位 t_s 或 %s，標頭是：%s\n", yCol.c_str(),
                     header.c_str());
        return 1;
    }

    std::vector<double> t;
    std::vector<double> y;
    std::string line;
    while (std::getline(in, line))
    {
        if (line.empty())
        {
            continue;
        }
        t.push_back(cellAt(line, iT));
        y.push_back(cellAt(line, iY));
    }

    if (t.size() < 10)
    {
        std::fprintf(stderr, "%s 只有 %zu 列，太少\n", path, t.size());
        return 1;
    }

    const thermal::Fopdt f = thermal::identifyTwoPoint(t, y, stepAt, du);
    std::printf("k=%.6f\ntau=%.4f\ntheta=%.4f\nresidual_rms=%.6f\n", f.k, f.tau,
                f.theta, f.residualRms);
    return 0;
}
