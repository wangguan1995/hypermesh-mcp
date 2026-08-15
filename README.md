# hypermesh-mcp

HyperMesh MCP server，提供 CAD/CAE 相关能力，当前核心功能：

- **STP 导入转 HM**：通过 HyperMesh `hmbatch.exe` 将 `.stp` / `.step` 零件模型转换为 `.hm` 文件。
- **全自动网格划分 workflow**：`generate_mesh` 工具按 `workflow_params.json` 参数执行探测 → 分类 → 网格生成 → 保存的完整流程。
- **MCP server**：`hypermesh_mcp_server.py` 暴露 MCP 工具接口。

## 依赖

- Altair HyperWorks / HyperMesh（`hmbatch.exe`，默认路径 `C:\Program Files\Altair\2026\hwdesktop\hm\bin\win64\hmbatch.exe`）
- Python 3.10+

## 核心文件

| 文件 | 说明 |
| --- | --- |
| `convert_stp_to_hm.py` | STP→HM 命令行转换工具，支持中文文件名自动转 ASCII |
| `hypermesh_mcp_server.py` | MCP server，暴露 MCP 工具 |
| `run_full_meshing_workflow.py` | 全自动网格划分 workflow（`generate_mesh` 工具调用） |
| `workflow_params.json` | workflow 参数配置 |

## 快速开始

```bash
# 命令行转换
python convert_stp_to_hm.py 零件.stp [output.hm] [--hmbatch <path>]

# 启动 MCP server
python hypermesh_mcp_server.py
```

## 测试用例

`test_part.stp` 用于验证 STP 导入转换工具。

## DeepSeek Harness 插件

本仓库被打上 `dsh-plugin` topic，可作为 DeepSeek Harness (dsh) 插件使用。