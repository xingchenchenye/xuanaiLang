from __future__ import annotations

import unittest

from xuanlang.transpilers import PythonToXuanTranslator


class TranspilerTests(unittest.TestCase):
    def test_python_to_xuan_subset(self) -> None:
        source = """
def 加法(a: int, b: int) -> int:
    return a + b

值 = 加法(2, 3)
"""
        result = PythonToXuanTranslator().translate(source)
        self.assertIn("术 加法(a: 整, b: 整) -> 整 {", result)
        self.assertIn("令 值 = 加法(2, 3)；", result)

    def test_python_for_print_translation(self) -> None:
        source = """
for i in range(3):
    print(i)
"""
        result = PythonToXuanTranslator().translate(source)
        self.assertIn("遍 i 于 范(3) {", result)
        self.assertIn("显(i)；", result)

    def test_python_dict_translation(self) -> None:
        source = """
cfg: dict[str, int] = {"层": 7, "头": 8}
"""
        result = PythonToXuanTranslator().translate(source)
        self.assertIn('令 cfg: 映[文, 整] = {"层": 7, "头": 8}；', result)

    def test_python_assignment_target_translation(self) -> None:
        source = """
cfg = {"层": 7}
cfg["层"] = 8
cfg.作者 = "星尘"
"""
        result = PythonToXuanTranslator().translate(source)
        self.assertIn('令 cfg = {"层": 7}；', result)
        self.assertIn('cfg["层"] = 8；', result)
        self.assertIn('cfg.作者 = "星尘"；', result)


if __name__ == "__main__":
    unittest.main()
