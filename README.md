# Gemini PDF Understanding MCP Server

MCP server để hiểu và phân tích PDF bằng Google Gemini API. **1 tool duy nhất** - tự động xử lý 1 hoặc nhiều PDFs.

## 🌟 Tính Năng

- **Single Tool Workflow**: URL + Prompt → Kết quả (1 bước)
- **Multiple PDFs Support**: So sánh và phân tích nhiều PDFs cùng lúc
- **Smart Caching**: Tự động cache file để tăng tốc lần sau
- **Hiểu PDF toàn diện**: Phân tích văn bản, hình ảnh, sơ đồ, biểu đồ, bảng
- **Tóm tắt & Trích xuất**: Tóm tắt nội dung, trích xuất thông tin có cấu trúc
- **Q&A**: Trả lời câu hỏi về tài liệu
- **Chuyển đổi**: Chuyển PDF sang HTML, text, v.v.
- **Lớn**: Hỗ trợ PDF lên đến 1,000 trang mỗi file
- **Tối ưu**: Sử dụng Google SDK chính thức + File API

## 🚀 Cài Đặt Nhanh

```bash
cd gemini-pdf-mcp-server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp env.example .env
# Sửa .env, thêm GEMINI_API_KEY của bạn
python main.py
```

## 🔑 Lấy API Key

1. Truy cập: https://aistudio.google.com/app/apikey
2. Đăng nhập Google Account
3. Click "Create API Key"
4. Copy và paste vào file `.env`

**Miễn phí**: 15 requests/phút, 1.5K requests/ngày

## 📖 Sử Dụng

### Workflow: 1 Bước (Đơn Giản)

**Input**: URL + Prompt → **Output**: Kết quả

### Tool: `understand_pdf_from_url`

**Mô tả**: Hiểu và phân tích 1 hoặc nhiều PDF từ URL (tự động xử lý mọi thứ)

**Parameters**:
- `pdf_url` (string hoặc list[string], required): 
  - String: 1 PDF
  - List: Nhiều PDFs
- `prompt` (string, required): Câu hỏi/yêu cầu về PDF(s)
- `model` (string, optional): Model Gemini (mặc định: `gemini-1.5-flash-latest`)

**Output**: Kết quả phân tích PDF(s)

**Use Cases**:
- **Single PDF**: Tóm tắt, trích xuất, Q&A, chuyển đổi
- **Multiple PDFs**: So sánh, tìm chủ đề chung, cross-reference

**Examples**:

```python
# Ví dụ 1: Tóm tắt PDF
{
  "tool": "understand_pdf_from_url",
  "arguments": {
    "pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",
    "prompt": "Tóm tắt bài báo này thành 3 đoạn văn"
  }
}

# Ví dụ 2: Trích xuất thông tin
{
  "tool": "understand_pdf_from_url",
  "arguments": {
    "pdf_url": "https://example.com/report.pdf",
    "prompt": "Trích xuất tất cả ngày tháng, tên người và số tiền"
  }
}

# Ví dụ 3: Phân tích (cùng URL, câu hỏi khác - sẽ dùng cache)
{
  "tool": "understand_pdf_from_url",
  "arguments": {
    "pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",
    "prompt": "Các phát hiện chính trong nghiên cứu này là gì?"
  }
}

# Ví dụ 4: Chuyển đổi
{
  "tool": "understand_pdf_from_url",
  "arguments": {
    "pdf_url": "https://example.com/doc.pdf",
    "prompt": "Chuyển sang HTML giữ nguyên layout"
  }
}

# Ví dụ 5: So sánh nhiều PDFs (dùng list)
{
  "tool": "understand_pdf_from_url",
  "arguments": {
    "pdf_url": [
      "https://arxiv.org/pdf/1706.03762.pdf",
      "https://arxiv.org/pdf/2010.11929.pdf"
    ],
    "prompt": "So sánh hai bài báo này. Điểm giống và khác nhau về phương pháp là gì?"
  }
}

# Ví dụ 6: Tìm chủ đề chung
{
  "tool": "understand_pdf_from_url",
  "arguments": {
    "pdf_url": [
      "https://example.com/paper1.pdf",
      "https://example.com/paper2.pdf",
      "https://example.com/paper3.pdf"
    ],
    "prompt": "Chủ đề chung xuyên suốt trong 3 bài báo này là gì?"
  }
}

# Ví dụ 7: Tóm tắt nhiều tài liệu
{
  "tool": "understand_pdf_from_url",
  "arguments": {
    "pdf_url": [
      "https://company.com/report-q1.pdf",
      "https://company.com/report-q2.pdf",
      "https://company.com/report-q3.pdf",
      "https://company.com/report-q4.pdf"
    ],
    "prompt": "Tóm tắt xu hướng kinh doanh qua 4 quý trong năm"
  }
}
```

## 📝 Cấu Trúc File

```
gemini-pdf-mcp-server/
├── main.py           # MCP server (1 tool duy nhất)
├── requirements.txt  # Dependencies
├── env.example      # Template cấu hình
├── .env             # Cấu hình thực (tạo từ env.example)
├── README.md        # File này
└── .gitignore       # Git ignore
```

## 🔧 Cấu Hình

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | ✅ Yes | - | API Key từ Google Gemini |

### API Limits (Free Tier)

- **RPM**: 15 requests/phút
- **TPM**: 1 triệu tokens/phút  
- **RPD**: 1,500 requests/ngày
- **Pages**: Tối đa 1,000 trang/PDF
- **Token**: 258 tokens/trang
- **File Storage**: Files được lưu tạm thời trên Gemini

### Lợi Ích

- ✅ **Cực kỳ đơn giản**: Chỉ 1 tool cho mọi use case
- ✅ **Tự động detect**: String = 1 PDF, List = nhiều PDFs
- ✅ **Không giới hạn**: Hỗ trợ nhiều PDFs (paid API key)
- ✅ **Smart caching**: Tự động cache, lần sau nhanh hơn
- ✅ **Tương thích hoàn hảo**: Với ai-native-todo-task-agent
- ✅ **Hiệu quả**: File API + caching + Google SDK

## 🐛 Xử Lý Lỗi

### "GEMINI_API_KEY is not configured"
→ Kiểm tra file `.env` có API key đúng

### "Rate limit exceeded"
→ Đợi 1 phút (free tier: 15 RPM)

### "Failed to download PDF"
→ Kiểm tra URL có public không

### "Request timeout"
→ PDF quá lớn hoặc kết nối chậm, thử lại

## 💡 Tips

- **Prompt rõ ràng**: "Tóm tắt 3 đoạn, mỗi đoạn 100 từ" thay vì "Tóm tắt"
- **PDF quality**: Dùng PDF rõ ràng, không bị mờ
- **Orientation**: Xoay trang đúng hướng trước khi upload
- **Rate limit**: Space out requests 4-5 giây

## 🔒 Bảo Mật

- ❌ Không commit file `.env`
- ❌ Không share API key công khai
- ✅ Dùng environment variables

## 📚 Tài Liệu

- [Gemini Document Processing](https://ai.google.dev/gemini-api/docs/document-processing?hl=vi)
- [Get API Key](https://aistudio.google.com/app/apikey)
- [Gemini API Docs](https://ai.google.dev/gemini-api)

## ✨ Credits

- [FastMCP](https://github.com/jlowin/fastmcp) - MCP framework
- [Google Gemini API](https://ai.google.dev/gemini-api) - AI capabilities

---

**Note**: Unofficial MCP server for Google Gemini API.
