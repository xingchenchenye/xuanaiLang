# 贡献指南

欢迎为 `玄言 / XuanLang` 贡献代码、文档、示例和测试。

## 基本流程

1. Fork 仓库并建立分支
2. 修改后运行测试
3. 保持代码和文档同步
4. 提交 Pull Request

## 本地检查

```powershell
py -3 -m unittest discover -s tests -v
py -3 -m xuanlang check .\examples\ai核心.xy
py -3 -m xuanlang fmt .\examples\快速开始.xy --check
```

## 贡献建议

- 新语法一定要补测试
- 新运行时能力尽量附带示例
- 高风险改动先写设计说明

开发者署名基线：`开发者星尘_尘夜`
