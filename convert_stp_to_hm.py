#!/usr/bin/env python
"""
将 .stp / .step 文件通过 HyperMesh 转换为 .hm 文件，并在转换成功后
自动用 HyperMesh GUI (runhwx.exe) 打开。

用法:
    python convert_stp_to_hm.py 零件.stp                  -> 输出 part_{hash}.hm，自动打开 GUI
    python convert_stp_to_hm.py part.stp                   -> 输出 part.hm，自动打开 GUI
    python convert_stp_to_hm.py 零件.stp  output.hm        -> 自定义输出路径

注意:
    如果 .stp 文件名是中文，输出的 .hm 文件名会替换为 "part_{hash}" 纯 ASCII。
    如需有意义的英文名，将映射表 _CH2EN 从空字典改为填充状态（见下方注释）。

可选中英文映射表:
    _CH2EN = {
        "零件": "part",
        "齿轮": "gear",
        "轴":   "shaft",
        "壳体": "housing",
        "法兰": "flange",
        "轴承": "bearing",
        # ... 按需添加
    }
"""

import argparse
import hashlib
import shutil
import sys
import tempfile
import time
from pathlib import Path

# ── 配置区 ──────────────────────────────────────────────────────────

# 中文→英文映射，为空则未知中文一律生成 "part_{hash}"
# 用户可自行在此填充
_CH2EN: dict[str, str] = {
    "零件": "part",
    "齿轮": "gear",
    "轴": "shaft",
    "壳体": "housing",
    "壳体零件": "housing",
    "法兰": "flange",
    "轴承": "bearing",
    "螺栓": "bolt",
    "螺母": "nut",
    "垫片": "washer",
    "弹簧": "spring",
    "活塞": "piston",
    "连杆": "connecting_rod",
    "凸轮": "cam",
    "键": "key",
    "齿轮轴": "gear_shaft",
    "支座": "bracket",
    "底座": "base",
    "盖板": "cap",
    "端盖": "end_cap",
    "法兰盘": "flange_disc",
    "泵体": "pump_body",
    "阀体": "valve_body",
}

# ── 工具函数 ─────────────────────────────────────────────────────────

def _has_non_ascii(path: str) -> bool:
    """检查路径是否包含非 ASCII 字符"""
    try:
        path.encode("ascii")
        return False
    except UnicodeEncodeError:
        return True


def _stem_to_safe_ascii(stem: str) -> str:
    """将可能含中文的 stem → 纯 ASCII 英文名或 uid"""
    if not _has_non_ascii(stem):
        return stem
    # 查找 _CH2EN 精确匹配
    if stem in _CH2EN:
        return _CH2EN[stem]
    # 查找最长子串匹配
    best_en = None
    best_len = 0
    for zh, en in _CH2EN.items():
        if zh in stem and len(zh) > best_len:
            best_en = en
            best_len = len(zh)
    if best_en:
        return best_en
    # fallback: uid
    hx = hashlib.md5(stem.encode("utf-8")).hexdigest()[:8]
    return f"part_{hx}"


def locate_hmbatch() -> Path:
    candidate = [
        r"C:\Program Files\Altair\2026\hwdesktop\hm\bin\win64\hmbatch.exe",
    ]
    for p in candidate:
        if Path(p).exists():
            return Path(p)
    raise FileNotFoundError(
        "找不到 hmbatch.exe。请修改 locate_hmbatch() 中的路径。\n"
        "常见位置: C:\\Program Files\\Altair\\<版本>\\hwdesktop\\hm\\bin\\win64\\hmbatch.exe"
    )


def locate_runhwx() -> Path:
    """定位 HyperMesh GUI 启动器 — 优先 hw.exe（HyperWorks Desktop）"""
    # hw.exe 是 HyperWorks 桌面入口，自动加载 HyperMesh 模块
    candidate = [
        r"C:\Program Files\Altair\2026\hwdesktop\hw\bin\win64\hw.exe",
        r"C:\Program Files\Altair\2026\hwdesktop\hwx\bin\win64\runhwx.exe",
        r"C:\Program Files\Altair\2026\common\framework\win64\hwx\bin\win64\runhwx.exe",
    ]
    for p in candidate:
        if Path(p).exists():
            return Path(p)
    return None  # 不是错误：GUI 打开可选


# ── 运行 hmbatch ─────────────────────────────────────────────────────

def run_hmbatch(hmbatch_path: Path, script: str, timeout: int = 120) -> dict:
    """执行 hmbatch -nojournal -tmpdir runs -tcl 'script' 并返回结果。"""
    import subprocess
    runs_dir = Path(__file__).parent / "runs"
    runs_dir.mkdir(exist_ok=True)

    script_path = runs_dir / f"_convert_tmp_{int(time.time()*1000)}.tcl"
    script_path.write_text(script, encoding="utf-8")
    print("BKP", [str(hmbatch_path), "-nojournal", "-tmpdir", str(runs_dir), "-tcl", str(script_path)])
    proc = subprocess.run(
        [str(hmbatch_path), "-nojournal", "-tmpdir", str(runs_dir), "-tcl", str(script_path)],
        capture_output=True, text=True, timeout=timeout,
    )

    # 清理临时 tcl
    try:
        script_path.unlink()
    except Exception:
        pass

    # 解析关键日志
    success = proc.returncode == 0
    info = {}
    for line in (proc.stdout + proc.stderr).splitlines():
        for kw in ("MCP_COUNTS",):
            if line.startswith(kw):
                info[kw] = " ".join(line.split()[1:]) if " " in line else ""
    return {
        "success": success,
        "returncode": proc.returncode,
        "info": info,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


# ── 从 .stp 生成 .hm ─────────────────────────────────────────────────

def convert_stp_to_hm(stp_path: Path, hm_path: Path, hmbatch_path: Path) -> dict:
    """导入 .stp，导出为 .hm，返回结果。

    如果 hm_path 已存在，**不删除也不覆盖**，自动加 _v2 / _v3 ... 后缀。
    """
    # 避让已有文件: part.hm → part_v2.hm / part_v3.hm ...
    actual_hm_path = hm_path
    if hm_path.exists():
        base = hm_path.name      # e.g. "part.hm"
        stem = base[:base.rfind('.')]  # e.g. "part"
        ext = base[base.rfind('.'):] # e.g. ".hm"
        counter = 2
        while True:
            candidate = hm_path.parent / f"{stem}_v{counter}{ext}"
            if not candidate.exists():
                print(f"注意: {hm_path} 已存在，自动改名为 {candidate.name}")
                actual_hm_path = candidate
                break
            counter += 1

    tcl = f"""
set mcp_stp_path [file normalize {{{stp_path.resolve().as_posix()}}}]
set mcp_hm_path [file normalize {{{actual_hm_path.resolve().as_posix()}}}]

puts "MCP_IMPORT_BEGIN stp=$mcp_stp_path"

if {{[catch {{*feinputwithdata2 "#Detect" $mcp_stp_path 1 0 -0.01 0 0 1 0 1 0}} err]}} {{
    puts "IMPORT_ERROR $err"
    error $err
}}

*createmark solids 1 all
set solid_count [llength [hm_getmark solids 1]]
*createmark surfs 1 all
set surf_count [llength [hm_getmark surfs 1]]
puts "MCP_COUNTS solids=$solid_count surfs=$surf_count"

*writefile "$mcp_hm_path" 2
puts "MCP_DONE output=$mcp_hm_path"
""".lstrip()

    return run_hmbatch(hmbatch_path, tcl), actual_hm_path


# ── 主程序 ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        "将 .stp/.step 文件通过 HyperMesh 转换为 .hm 文件，并自动用 GUI 打开。",
    )
    parser.add_argument("input", help="输入的 .stp 或 .step 文件路径")
    parser.add_argument("output", nargs="?", default=None,
                        help="输出的 .hm 文件路径 (默认: 同名.hm)")
    parser.add_argument("--hmbatch", default=None,
                        help="hmbatch.exe 路径 (默认: 自动检测)")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"错误: 文件不存在: {input_path}")
        sys.exit(1)

    # ── 步骤1: 输入路径/文件名有中文 → 拷贝到纯 ASCII 临时目录 ──
    if _has_non_ascii(str(input_path)):
        tmp_dir = Path(tempfile.gettempdir()) / "hmcp"
        tmp_dir.mkdir(exist_ok=True)
        safe_stp = tmp_dir / input_path.name
        shutil.copy2(str(input_path), str(safe_stp))
        print(f"注意: 输入路径/文件名含非 ASCII 字符，已拷贝到 {safe_stp}")
        input_path = safe_stp

    ext = input_path.suffix.lower()
    if ext not in (".stp", ".step", ".hm"):
        if ext == ".step":
            ext = ".stp"
        else:
            print(f"错误: 不支持的文件格式 {ext}，仅支持 .stp / .step / .hm")
            sys.exit(1)

    # ── 步骤2: 输出路径必须纯 ASCII ──
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = input_path.parent / f"{input_path.stem}.hm"

    original_input_stem = input_path.stem
    renamed_output = False

    # 检查输出路径是否纯 ASCII
    need_renaming = _has_non_ascii(str(output_path.parent)) or _has_non_ascii(str(output_path))
    if need_renaming or (not args.output and _has_non_ascii(original_input_stem)):
        safe_stem = _stem_to_safe_ascii(original_input_stem)
        if _has_non_ascii(str(output_path.parent)):
            tmp_dir = Path(tempfile.gettempdir()) / "hmcp"
            tmp_dir.mkdir(exist_ok=True)
            output_path = tmp_dir / f"{safe_stem}.hm"
        else:
            output_path = output_path.parent / f"{safe_stem}.hm"
        renamed_output = True

    # 定位 hmbatch
    if args.hmbatch:
        hmbatch_path = Path(args.hmbatch)
    else:
        hmbatch_path = locate_hmbatch()

    if not hmbatch_path.exists():
        print(f"错误: hmbatch.exe 不存在: {hmbatch_path}")
        sys.exit(1)

    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    print(f"hmbatch: {hmbatch_path}")
    print()

    # 执行转换（返回结果 + 实际输出路径）
    result, actual_hm_path = convert_stp_to_hm(input_path, output_path, hmbatch_path)

    # 打印结果
    print("=" * 60)
    print(f"Return code: {result['returncode']}")
    print(f"Success:     {result['success']}")
    for k, v in result['info'].items():
        print(f"  {k}: {v}")
    if result['stdout']:
        print(f"stdout: {result['stdout'][:500]}")
    if result['stderr']:
        print(f"stderr: {result['stderr'][:500]}")

    # 成功 → 提示双击打开
    if result['success'] and actual_hm_path.exists():
        size_mb = actual_hm_path.stat().st_size / 1024 / 1024
        msg = f"转换成功! 输出文件: {actual_hm_path} ({size_mb:.2f} MB)"
        if renamed_output:
            msg += "  (文件名已自动转为纯 ASCII)"
        if actual_hm_path != output_path:
            msg += f"  (原路径 {output_path.name} 已保留，新版本已避让为 {actual_hm_path.name})"
        print(f"\n{msg}")
        print(f"\n请在资源管理器中双击 {actual_hm_path} 用 HyperMesh GUI 打开。")
    elif not result['success']:
        print(f"\n转换失败! (returncode={result['returncode']})")
        sys.exit(1)


if __name__ == "__main__":
    main()
