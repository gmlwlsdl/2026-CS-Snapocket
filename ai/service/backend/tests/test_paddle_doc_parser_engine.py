import sys
import types
import unittest

from app.services.ocr.paddle_doc_parser_engine import PaddleOCRVLDocParserEngine


class PaddleDocParserEngineConfigTests(unittest.TestCase):
    def test_passes_vl_rec_concurrency_and_generation_limit_to_paddle(self):
        captured = {}

        class FakePaddleOCRVL:
            def __init__(self, **kwargs):
                captured["init_kwargs"] = kwargs

            def predict(self, source_path, **kwargs):
                captured["predict_kwargs"] = kwargs
                return [
                    {
                        "parsing_res_list": [
                            {
                                "block_content": "hello",
                                "block_label": "text",
                                "block_order": 1,
                            }
                        ]
                    }
                ]

        fake_module = types.ModuleType("paddleocr")
        fake_module.PaddleOCRVL = FakePaddleOCRVL
        original_module = sys.modules.get("paddleocr")
        sys.modules["paddleocr"] = fake_module
        try:
            engine = PaddleOCRVLDocParserEngine(
                vl_rec_max_concurrency=1,
                max_new_tokens=384,
            )
            engine.available = lambda: True

            result = engine.infer_image(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
                b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT"
                b"\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfe"
                b"\xdc\xccY\xe7\x00\x00\x00\x00IEND\xaeB`\x82"
            )
        finally:
            if original_module is None:
                sys.modules.pop("paddleocr", None)
            else:
                sys.modules["paddleocr"] = original_module

        self.assertEqual(result[0].text, "hello")
        self.assertEqual(captured["init_kwargs"]["vl_rec_max_concurrency"], 1)
        self.assertEqual(captured["predict_kwargs"]["max_new_tokens"], 384)


if __name__ == "__main__":
    unittest.main()
