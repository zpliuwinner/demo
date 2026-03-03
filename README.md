# Amazon Related ASIN Crawler

输入一个 Amazon ASIN，从对应详情页提取“相关商品”的 ASIN（并做去重）。

## 使用

```bash
python amazon_related_asin_spider.py B08N5WRWNW --marketplace com --json
```

常用参数：

- `--marketplace`: 站点后缀（如 `com`, `co.uk`, `de`, `jp`）
- `--max-related`: 最多返回多少个 related ASIN（默认 30）
- `--sleep`: 请求前 sleep 秒数（礼貌抓取）
- `--timeout`: 超时时间（秒）
- `--json`: JSON 格式输出

## 说明

- 这是 **stdlib-only** 实现（不依赖第三方包）。
- 优先从页面里与推荐模块关键词相关的片段（`sims`, `p13n`, `sp_detail`, `related` 等）提取 ASIN；如果太少，会回退到整页 `data-asin` 与 `/dp/<ASIN>` 链接提取。
- Amazon 会有反爬策略（验证码、返回不完整页面、地区/登录限制），建议控制频率并加重试/代理。
