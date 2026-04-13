from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .codegen import PythonCodeGenerator
from .formatter import SourceFormatter
from .interpreter import Interpreter
from .ir import IRLowerer
from .lexer import Lexer
from .optimizer import AstOptimizer
from .parser import Parser
from .runtime.prelude import ModuleLoader
from .semantic import SemanticAnalyzer
from .vm import BytecodeCompiler, BytecodeDisassembler, VirtualMachine


class CompilerPipeline:
    def __init__(self, loader: ModuleLoader | None = None) -> None:
        self.loader = loader or ModuleLoader()

    def lex(self, source: str):
        return Lexer(source).tokenize()

    def parse(self, source: str):
        tokens = self.lex(source)
        return Parser(tokens).parse()

    def analyze(self, source: str):
        program = self.parse(source)
        SemanticAnalyzer().analyze(program)
        return program

    def check(self, source: str) -> bool:
        self.analyze(source)
        return True

    def symbol_table(self, source: str) -> dict[str, str]:
        program = self.parse(source)
        analyzer = SemanticAnalyzer()
        analyzer.analyze(program)
        return analyzer.snapshot_global_symbols()

    def optimize(self, source: str):
        program = self.analyze(source)
        return AstOptimizer().optimize(program)

    def build_ir(self, source: str):
        program = self.optimize(source)
        return IRLowerer().lower(program)

    def build_bytecode(self, source: str):
        program = self.optimize(source)
        return BytecodeCompiler().compile_program(program)

    def compile_source(self, source: str, source_path: str = "<memory>") -> str:
        program = self.optimize(source)
        return PythonCodeGenerator().generate(program, source_path=source_path)

    def compile_file(self, path: str) -> str:
        source_path = Path(path).resolve()
        source = source_path.read_text(encoding="utf-8")
        return self.compile_source(source, source_path=str(source_path))

    def execute_source(self, source: str, file_path: str = "<memory>", module_name: str = "__main__") -> dict[str, Any]:
        program = self.optimize(source)
        env = Interpreter(loader=self.loader).execute(program, file_path=file_path, module_name=module_name)
        env["__compiled_python__"] = self.compile_source(source, source_path=file_path)
        return env

    def execute_source_python(self, source: str, file_path: str = "<memory>", module_name: str = "__main__") -> dict[str, Any]:
        python_source = self.compile_source(source, source_path=file_path)
        env: dict[str, Any] = {
            "__name__": module_name,
            "__file__": file_path,
            "__xuan_file__": file_path,
            "__xuan_loader__": self.loader,
        }
        exec(compile(python_source, file_path, "exec"), env, env)
        env["__compiled_python__"] = python_source
        env["__backend__"] = "python"
        return env

    def execute_source_vm(self, source: str, file_path: str = "<memory>", module_name: str = "__main__") -> dict[str, Any]:
        bytecode = self.build_bytecode(source)
        env = VirtualMachine(loader=self.loader).execute(bytecode, file_path=file_path, module_name=module_name)
        env["__bytecode__"] = BytecodeDisassembler().format_block(bytecode)
        return env

    def execute_file(self, path: str, module_name: str | None = None) -> dict[str, Any]:
        source_path = Path(path)
        source = source_path.read_text(encoding="utf-8")
        return self.execute_source(source, str(source_path.resolve()), module_name or source_path.stem)

    def execute_file_python(self, path: str, module_name: str | None = None) -> dict[str, Any]:
        source_path = Path(path)
        source = source_path.read_text(encoding="utf-8")
        return self.execute_source_python(source, str(source_path.resolve()), module_name or source_path.stem)

    def execute_file_vm(self, path: str, module_name: str | None = None) -> dict[str, Any]:
        source_path = Path(path)
        source = source_path.read_text(encoding="utf-8")
        return self.execute_source_vm(source, str(source_path.resolve()), module_name or source_path.stem)

    def ast_to_data(self, source: str) -> Any:
        program = self.parse(source)
        return self._to_data(program)

    def optimized_ast_to_data(self, source: str) -> Any:
        program = self.optimize(source)
        return self._to_data(program)

    def disassemble(self, source: str) -> str:
        bytecode = self.build_bytecode(source)
        return BytecodeDisassembler().format_block(bytecode)

    def format_source(self, source: str) -> str:
        program = self.analyze(source)
        return SourceFormatter().format_program(program)

    def _to_data(self, value: Any) -> Any:
        if is_dataclass(value):
            return {key: self._to_data(item) for key, item in asdict(value).items()}
        if isinstance(value, list):
            return [self._to_data(item) for item in value]
        if isinstance(value, tuple):
            return [self._to_data(item) for item in value]
        return value
