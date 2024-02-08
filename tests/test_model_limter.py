import unittest
import time
from mypylib.google_ai import ModelRateLimiter


class TestModelRateLimiter(unittest.TestCase):
    def setUp(self):
        self.rate_limiter = ModelRateLimiter(2, 1)  # 允许每秒2次调用

    def test_rate_limiting(self):
        model_name = "test_model"
        func = lambda: "Hello, World!"

        # 第一次和第二次调用应该立即返回
        start_time = time.time()
        self.assertEqual(self.rate_limiter.call_func(model_name, func), "Hello, World!")
        self.assertEqual(self.rate_limiter.call_func(model_name, func), "Hello, World!")
        self.assertLess(time.time() - start_time, 1)

        # 第三次调用应该等待至少1秒
        start_time = time.time()
        self.assertEqual(self.rate_limiter.call_func(model_name, func), "Hello, World!")
        self.assertGreaterEqual(time.time() - start_time, 1)


if __name__ == "__main__":
    unittest.main()
