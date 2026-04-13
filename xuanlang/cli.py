from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import CompilerPipeline
from .project import ProjectManager


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="玄言")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("run", "runpy", "runvm", "check", "tokens", "ast", "optast", "ir", "symbols", "asm"):
        cmd = sub.add_parser(name)
        cmd.add_argument("target")

    build = sub.add_parser("build")
    build.add_argument("target")
    build.add_argument("-o", "--output", required=True)

    py2x = sub.add_parser("py2xuan")
    py2x.add_argument("target")
    py2x.add_argument("-o", "--output")

    new = sub.add_parser("new")
    new.add_argument("path")

    fmt = sub.add_parser("fmt")
    fmt.add_argument("target")
    fmt.add_argument("--check", action="store_true")

    test_cmd = sub.add_parser("test")
    test_cmd.add_argument("target", nargs="?", default=".")

    sub.add_parser("about")

    args = parser.parse_args(argv)
    pipeline = CompilerPipeline()
    projects = ProjectManager()
    if args.command == "about":
        print("玄言 / XuanLang 0.7.0")
        print("开发者星尘_尘夜")
        print("方向: AI 原生、中英融合、高密度表达、可演进编译链、独立 VM 执行层、原生映射系统、复杂左值赋值、结构体系统")
        return 0

    if args.command == "new":
        from .scaffold import ProjectScaffolder

        root = ProjectScaffolder().create(args.path)
        print(f"已创建玄言项目: {root}")
        return 0
    if args.command == "test":
        tests = projects.discover_tests(args.target)
        if not tests:
            print("未发现玄言测试文件")
            return 1
        failed = 0
        for file in tests:
            try:
                pipeline.execute_file(file)
                print(f"通过: {file}")
            except Exception as error:
                failed += 1
                print(f"失败: {file}")
                print(error)
        if failed:
            print(f"测试失败: {failed}/{len(tests)}")
            return 1
        print(f"测试通过: {len(tests)}")
        return 0

    if args.command == "fmt":
        source_path = projects.resolve_source(args.target) if Path(args.target).is_dir() else Path(args.target).resolve()
        original = source_path.read_text(encoding="utf-8")
        formatted = pipeline.format_source(original)
        changed = formatted != original
        if args.check:
            print("需要格式化" if changed else "格式已规范")
            return 1 if changed else 0
        source_path.write_text(formatted, encoding="utf-8")
        print(f"已格式化: {source_path}")
        return 0

    source_path = projects.resolve_source(args.target) if Path(args.target).is_dir() else Path(args.target).resolve()
    source = source_path.read_text(encoding="utf-8")

    if args.command == "run":
        pipeline.execute_source(source, str(source_path))
        return 0
    if args.command == "runpy":
        pipeline.execute_source_python(source, str(source_path))
        return 0
    if args.command == "runvm":
        pipeline.execute_source_vm(source, str(source_path))
        return 0
    if args.command == "check":
        pipeline.check(source)
        print("检查通过")
        return 0
    if args.command == "tokens":
        for token in pipeline.lex(source):
            print(f"{token.line}:{token.column}\t{token.kind.name}\t{token.value}")
        return 0
    if args.command == "ast":
        print(json.dumps(pipeline.ast_to_data(source), ensure_ascii=False, indent=2))
        return 0
    if args.command == "optast":
        print(json.dumps(pipeline.optimized_ast_to_data(source), ensure_ascii=False, indent=2))
        return 0
    if args.command == "ir":
        for inst in pipeline.build_ir(source):
            print(inst)
        return 0
    if args.command == "symbols":
        print(json.dumps(pipeline.symbol_table(source), ensure_ascii=False, indent=2))
        return 0
    if args.command == "asm":
        print(pipeline.disassemble(source))
        return 0
    if args.command == "build":
        output = Path(args.output)
        output.write_text(
            pipeline.compile_source(source, source_path=str(source_path)),
            encoding="utf-8",
        )
        print(f"已生成: {output}")
        return 0
    if args.command == "py2xuan":
        from .transpilers import PythonToXuanTranslator

        text = PythonToXuanTranslator().translate(source)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
            print(f"已生成: {args.output}")
        else:
            print(text)
        return 0
    return 1
