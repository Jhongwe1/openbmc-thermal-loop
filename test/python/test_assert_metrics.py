"""assert_metrics.py 的守門測試 —— 釘死計算慣例與允收區間語意。

這裡釘的不是「數字對不對」(那是 assert_metrics 自己的工作),
而是「計算路徑不會被重構悄悄改掉語意」:

  · A/B 比值 = 逐 seed 配對後取中位數。配對版與「兩組中位數相除」版
    只差 ~0.4%(13.73 vs 13.79),寬鬆的容差兩個都放得過 ——
    所以釘死測試用 rel=1e-3,只有配對版過得了。
  · 負值宣稱的允收區間要先排序 —— 計畫 W10 範本的原始寫法在
    value<0 時 lo>hi,永遠 FAIL。mutation AM1 植回計畫的寫法。
  · 完整性是雙向的:每個 claim 都要有計算路徑,每條路徑都要有 claim。
  · 竄改要被抓到:值被改 30% 時 main() 必須非零離開(mutation AM3
    把失敗聚合改成「最後一個說了算」,靠 test_tampered 抓)。

對應 mutation:tools/mutation_check.sh 的 AM1~AM4。
"""

import json
import sys

import pandas as pd
import pytest

import assert_metrics as am


def test_registry_and_claims_are_bijective():
    """雙向完整性:宣稱 ↔ 計算路徑 一一對應。

    「沒有計算路徑的宣稱不該存在」是 assert_metrics 的存在理由;
    反向(殭屍計算路徑)則代表 claims.json 有東西被刪了而檢查碼沒跟上。
    """
    assert set(am.load_claims()) == set(am.COMPUTE)


def test_all_claims_recompute_within_band():
    """每一個 claim 從資料重算都要落在自己宣告的允收區間內。

    本機資料 = 產生宣稱的那批資料,重算本來就該過;
    這個測試在 CI 上跑時,資料是剛重跑出來的 —— 那才是它上工的時刻。
    """
    for name, c in am.load_claims().items():
        _mode, fn = am.COMPUTE[name]
        lo, hi = am.band(c["value"], c["tolerance_pct"])
        assert lo <= fn() <= hi, name


def test_paired_ratio_convention_pinned():
    """配對比值的慣例釘死(rel=1e-3 距「中位數相除」版 0.4% 夠遠)。"""
    claims = am.load_claims()
    for name in ("recover_s_ratio", "reversals_reduction_ratio"):
        _mode, fn = am.COMPUTE[name]
        assert fn() == pytest.approx(claims[name]["value"], rel=1e-3), name


def test_band_handles_negative_claims():
    """允收區間對負值宣稱要成立(fopdt_k < 0)。

    計畫範本 lo=v·(1−t)、hi=v·(1+t) 在 v<0 時上下顛倒;
    band() 的 sorted() 就是在修這個。AM1 把 sorted 拿掉後這裡會紅。
    """
    lo, hi = am.band(-0.3147, 0.05)
    assert lo < hi
    assert lo == pytest.approx(-0.3147 * 1.05)
    assert hi == pytest.approx(-0.3147 * 0.95)
    assert lo <= -0.3147 <= hi


def test_e2e_uses_only_non_warmup_reps():
    """e2e 的計算路徑必須排除暖身 rep(獨立重算比對,n 也要對)。"""
    df = pd.read_csv(am.DATA / "exp10_latency" / "events.csv")
    warm = df["warmup"].astype(str) == "True"
    assert int(warm.sum()) >= 1, "events.csv 裡連暖身列都沒有,這個測試守不到東西"
    assert int((~warm).sum()) == 28  # docs/measurement.md exp10:32 − 2 暖身 − 2 拒收
    expected = float(df.loc[~warm, "total_redfish_s"].median())
    _mode, fn = am.COMPUTE["e2e_inject_to_redfish_s"]
    assert fn() == expected


def test_failsafe_pinned_to_t2_minus_t0():
    """failsafe 宣稱的是 t2−t0(總延遲),不是 t1−t0(僅偵測)。

    兩者差恰好一個內圈週期 100 ms(≈2%),寬容差放得過 ——
    所以用 rel=1e-3 釘死。
    """
    claims = am.load_claims()
    _mode, fn = am.COMPUTE["failsafe_detect_s"]
    assert fn() == pytest.approx(claims["failsafe_detect_s"]["value"],
                                 rel=1e-3)


def test_tampered_claim_fails(monkeypatch, capsys):
    """值被改 30% → main() 必須回非零並點名該 claim。

    竄改的是**中段**的 claim(fopdt_tau_s):如果失敗聚合被改成
    「最後一個說了算」(AM3),後面全 PASS 會把它洗白 —— 這裡就會抓到。
    """
    tampered = json.loads(json.dumps(am.load_claims()))
    tampered["fopdt_tau_s"]["value"] *= 1.3
    monkeypatch.setattr(am, "load_claims", lambda: tampered)
    monkeypatch.setattr(sys, "argv", ["assert_metrics.py"])
    assert am.main() == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "fopdt_tau_s" in out


def test_only_unknown_claim_is_an_error(monkeypatch, capsys):
    """--only 打錯名字要報錯,不能「什麼都沒檢查」卻回 0。"""
    monkeypatch.setattr(sys, "argv",
                        ["assert_metrics.py", "--only", "no_such_claim"])
    assert am.main() == 1
    assert "no_such_claim" in capsys.readouterr().out
