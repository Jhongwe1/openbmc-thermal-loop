# 三條入口,對應 README「自己跑一次」的三行。
#
# 增益參數不用傳:exp05/07/08 自己從 bench/data/exp01_fit.txt 經
# bench/tune.py 導出 —— 手抄係數這件事在這個 repo 裡不存在。
# (計畫範本的 `make figures TUNE=...` 因此拿掉了。)

.PHONY: test figures qemu

test:
	meson setup build 2>/dev/null || true
	meson compile -C build
	meson test -C build --print-errorlogs

figures:
	python bench/exp01_sysid.py      --out bench/data
	python bench/exp05_tuning.py     --out bench/data
	python bench/exp07_antiwindup.py --out bench/data
	python bench/exp08_slew_sweep.py --out bench/data
	python bench/plot.py --all

qemu:
	./harness/qemu/fetch_image.sh bletchley
	./harness/qemu/run_bmc.sh bletchley
