"""bench/sim 的 CLI 行為 —— W7 的 `--power-down-at` 與 W8 的 `--power-profile`。

★ 為什麼用子行程跑執行檔，而不是把邏輯拆出來單元測
    sim.cpp 是「把參數翻譯成一次模擬」的黏合層，它會犯的錯都是黏合錯：
    旗標沒接上、條件寫反、驗證漏掉、參數沒進 stderr dump。
    單元測會把黏合層繞過去 —— 而黏合層正是這裡唯一要測的東西。
    成本可控：dt=0.5、50 秒只有 100 步，單次毫秒級。

⚠️ 這裡刻意不測任何「控制行為」——那是 test_closed_loop.cpp 的工作。
   同一件事有兩個測試守著的那天，其中一個就會開始說謊。
"""

import io
import pathlib
import subprocess

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
SIM = ROOT / "build" / "sim"


def run_sim(*extra: str) -> subprocess.CompletedProcess:
    assert SIM.exists(), (
        f"{SIM} 不存在 —— 先 `meson compile -C build`。"
        "這裡刻意 fail 而不是 skip：安靜跳過的測試等於沒有測試。")
    cmd = [str(SIM), "--dt", "0.5", "--seconds", "50", "--noise-sigma", "0",
           "--power-base", "150", "--power-step", "400", "--power-at", "10",
           *extra]
    return subprocess.run(cmd, capture_output=True, text=True)


def frame(proc: subprocess.CompletedProcess) -> pd.DataFrame:
    assert proc.returncode == 0, proc.stderr
    return pd.read_csv(io.StringIO(proc.stdout))


def test_power_down_at_returns_power_to_base():
    """防：降回條件不生效（mutation B1）。

    期望的負載曲線：t<10 → 150、10≤t<30 → 400、t≥30 → 150。
    三段都逐點檢查 —— 只驗尾段的話，「整段都是 base」的錯也會過。
    """
    df = frame(run_sim("--power-down-at", "30"))
    assert df.loc[df["t_s"] < 10.0, "power_w"].eq(150.0).all()
    mid = df[(df["t_s"] >= 10.0) & (df["t_s"] < 30.0)]
    assert len(mid) > 0 and mid["power_w"].eq(400.0).all()
    tail = df[df["t_s"] >= 30.0]
    assert len(tail) > 0 and tail["power_w"].eq(150.0).all()


def test_without_power_down_at_the_step_stays_up():
    """防：預設值誤啟用（例如預設寫成 0 會把整段都降回 base）。

    exp05 那批已進 git 的單段階躍資料就是這個行為 ——
    這一條等於守著「加新旗標沒有改變舊行為」。
    """
    df = frame(run_sim())
    assert df.loc[df["t_s"] >= 10.0, "power_w"].eq(400.0).all()


def test_power_down_before_the_step_up_is_rejected_loudly():
    """防：安靜接受顛倒的時序 —— 那批 CSV 看起來完全正常，還會被拿去畫圖。"""
    proc = run_sim("--power-down-at", "5")
    assert proc.returncode == 2
    assert "power-down-at" in proc.stderr


def test_power_down_at_without_power_at_is_rejected_loudly():
    """防：只給降回、沒給上去。沒有第一段階躍就沒有「降回來」可言。"""
    proc = subprocess.run(
        [str(SIM), "--dt", "0.5", "--seconds", "50", "--power-down-at", "30"],
        capture_output=True, text=True)
    assert proc.returncode == 2


def test_power_down_at_is_recorded_in_the_params_dump():
    """防：忘了進 stderr 參數 dump。

    exp07 的 meta 會少掉關鍵欄位，而 check_single_variable 比對的
    正是這份 dump —— 沒進 dump 的參數等於躲過了單變因檢查。
    """
    proc = run_sim("--power-down-at", "30")
    assert proc.returncode == 0
    assert "power_down_at=30" in proc.stderr


def test_open_loop_params_dump_is_unchanged_without_the_new_flag():
    """★ 防：新參數行**無條件**印出來。

    exp01 的 meta 檔已經進 git，「重跑 exp01 得到同一份 meta」是 Fig 1
    可重現宣稱的一部分。多印一行（哪怕是 power_down_at=-1）都會讓它作廢。
    """
    proc = run_sim()
    assert proc.returncode == 0
    assert "power_down_at" not in proc.stderr


# ── W8：--power-profile square ────────────────────────────────────────────


def test_square_alternates_between_step_and_base():
    """防三種波形錯（mutation S1~S3）：半週期忘了除 2（恆為 step）、
    step/base 顛倒、相位忘了以 power-at 為原點。

    --power-at 10、全週期 20 → 期望五段：
      t<10 → 150、10~20 → 400、20~30 → 150、30~40 → 400、40~50 → 150。
    ★ 相位錯（fmod(t) 而非 fmod(t−power_at)）在 10~20 段給的是 150，
      所以第二段的斷言同時守著三個 mutation —— 但五段全查，
      「只對到一半」的錯才沒有地方躲。
    """
    df = frame(run_sim("--power-profile", "square", "--power-period", "20"))
    segments = [(0, 10, 150.0), (10, 20, 400.0), (20, 30, 150.0),
                (30, 40, 400.0), (40, 50, 150.0)]
    for lo, hi, expect in segments:
        seg = df[(df["t_s"] >= lo) & (df["t_s"] < hi)]
        assert len(seg) > 0 and seg["power_w"].eq(expect).all(), (
            f"{lo}~{hi} s 應為 {expect} W：\n{seg[['t_s', 'power_w']]}")


def test_explicit_step_profile_matches_the_default():
    """防：profile 字串解析寫反（把 step 當 square 跑）。"""
    df = frame(run_sim("--power-profile", "step"))
    assert df.loc[df["t_s"] >= 10.0, "power_w"].eq(400.0).all()


def test_unknown_profile_is_rejected_loudly():
    """防：打錯字默默退回 step —— 40 份「以為是方波」的 CSV 看起來完全正常。"""
    proc = run_sim("--power-profile", "sqare")
    assert proc.returncode == 2
    assert "power-profile" in proc.stderr


def test_square_without_power_at_is_rejected_loudly():
    """防：沒有相位原點的方波。"""
    proc = subprocess.run(
        [str(SIM), "--dt", "0.5", "--seconds", "50",
         "--power-profile", "square"],
        capture_output=True, text=True)
    assert proc.returncode == 2
    assert "power-at" in proc.stderr


def test_square_with_power_down_at_is_rejected_loudly():
    """防：兩種負載語言混用時安靜選一邊。"""
    proc = run_sim("--power-profile", "square", "--power-down-at", "30")
    assert proc.returncode == 2


def test_nonpositive_power_period_is_rejected_loudly():
    """防：period=0 的 fmod 是 NaN，往下傳整條曲線都是垃圾。"""
    proc = run_sim("--power-profile", "square", "--power-period", "0")
    assert proc.returncode == 2


def test_power_period_in_step_mode_is_rejected_loudly():
    """防：step 模式安靜收下 --power-period —— 使用者以為自己跑了方波。"""
    proc = run_sim("--power-period", "20")
    assert proc.returncode == 2


def test_square_params_are_recorded_in_the_dump():
    """防：忘了進 stderr dump（mutation S4）。

    exp08 的 check_single_variable 比對的就是這份 dump ——
    這兩行不在，「八組都跑同一個方波」就沒有機器可查的證據。
    """
    proc = run_sim("--power-profile", "square", "--power-period", "20")
    assert proc.returncode == 0
    assert "power_profile=square" in proc.stderr
    assert "power_period=20" in proc.stderr


def test_params_dump_is_unchanged_without_square():
    """★ 同 power_down_at 那條：step 模式一行都不多印。
    exp01 / exp05 / exp07 的 meta 已進 git，重跑要逐 byte 相同。
    """
    proc = run_sim()
    assert proc.returncode == 0
    assert "power_profile" not in proc.stderr
    assert "power_period" not in proc.stderr
