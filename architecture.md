# Multi-Agent Architecture — Olist Dispute Resolution

## 1. Mục tiêu

Hệ thống xử lý 50 yêu cầu hỗ trợ theo EC_POLICY_V2. Mỗi agent chỉ phân tích
một domain dữ liệu và bàn giao kết quả có schema cho Coordinator. CSV Olist là
nguồn sự thật cho ID, timestamp và số tiền; hệ thống không suy diễn refund
transaction, tracking checkpoint hoặc bằng chứng giao thiếu vì dataset không
có các dữ liệu này.

Ba nguyên tắc thiết kế:

1. Tách trách nhiệm giữa các agent.
2. Handoff bằng Pydantic model thay vì dictionary tự do.
3. Chỉ ghi output sau khi Verifier kiểm tra lại với CSV.

## 2. Sơ đồ agent

    input/EC_*.json
            |
            v
    +--------------------+
    | CoordinatorAgent   |
    +--------------------+
       |       |       |
       |       |       +-------------------------------+
       |       |                                       |
       v       v                                       v
    Customer  OrderProduct                         DataStore
    Agent     Agent                             (read-only CSV)
                |
                +------------+-------------+
                |            |             |
                v            v             |
             Payment      Delivery         |
             Agent        Agent            |
                |            |             |
                +------+-----+             |
                       |                   |
                       v                   |
                  PolicyAgent              |
                       |                   |
                       v                   |
                Draft CaseOutput           |
                       |                   |
                       v                   |
                 LLMReviewAgent            |
                       |                   |
                       v                   |
                 VerifierAgent <-----------+
                       |
                       v
                output/EC_*.json

Mỗi case tạo 5 handoff từ các agent phân tích, 1 handoff từ LLMReviewAgent và
1 handoff từ Verifier, tổng cộng 7 event. Lượt chạy 50 case tạo 350 dòng trong
logging/trace.jsonl.

## 3. Vai trò, input, output và quyền truy cập

| Thành phần | Input | Output | Quyền truy cập |
|---|---|---|---|
| CoordinatorAgent | CaseInput | CaseOutput dự thảo | Chỉ gọi agent và tổng hợp handoff |
| CustomerAgent | order_id, include history | CustomerContext | orders, customers qua DataStore |
| OrderProductAgent | order_id, include product | OrderProductAnalysis | orders, items, products, sellers qua DataStore |
| PaymentAgent | OrderProductAnalysis | PaymentAnalysis | payments qua DataStore |
| DeliveryAgent | OrderProductAnalysis | DeliveryAnalysis | Không đọc CSV trực tiếp |
| PolicyAgent | Bốn analysis handoff | PolicyDecision | Không đọc CSV trực tiếp |
| LLMReviewAgent | CaseInput và CaseOutput dự thảo | LLMReview | Gọi OpenRouter Chat API bằng key trong `.env` |
| VerifierAgent | CaseOutput dự thảo | CaseOutput đã xác minh | Đọc lại orders, items, payments qua DataStore |
| TraceLogger | Handoff summary | JSONL event | Chỉ ghi logging/trace.jsonl |

Chỉ batch runner được ghi output. Các agent chuyên trách không được tự ghi file
hoặc thay đổi DataFrame nguồn.

## 4. DataStore

DataStore đọc mỗi CSV cần thiết một lần khi khởi tạo:

- olist_orders_dataset.csv
- olist_order_items_dataset.csv
- olist_order_payments_dataset.csv
- olist_customers_dataset.csv
- olist_products_dataset.csv
- olist_sellers_dataset.csv

ID được giữ dạng chuỗi. Price, freight và payment value được đọc dạng số thực.
Các phép lọc trả về bản sao và giữ nguyên thứ tự row trong dữ liệu nguồn.

## 5. Luồng handoff

### 5.1 Input

Input được kiểm tra bởi CaseInput:

- case_id có dạng EC_NNN.
- claimed_order_id có 32 ký tự hex.
- policy_version phải là EC_POLICY_V2.

### 5.2 Customer handoff

CustomerAgent nối orders.customer_id với customers.customer_id, lấy
customer_unique_id rồi tìm các order của cùng khách hàng. Order đang khiếu nại
bị loại và related_order_ids được giới hạn tối đa 5.

### 5.3 Order/product handoff

OrderProductAgent trả về order status, ba timestamp delivery, toàn bộ item,
seller, product và category. Các danh sách loại trùng nhưng giữ thứ tự nguồn.

### 5.4 Payment handoff

PaymentAgent tính:

    expected_total_brl = sum(price) + sum(freight_value)
    difference_brl = sum(payment_value) - expected_total_brl
    reconciled = abs(difference_brl) <= 0.10

Mọi số tiền làm tròn 2 chữ số. Nếu không có item, expected total, difference
và reconciled là null.

### 5.5 Delivery handoff

DeliveryAgent tính:

    delivery_variance_hours =
        delivered_customer_date - estimated_delivery_date

    handoff_variance_hours =
        delivered_carrier_date - shipping_limit_date sớm nhất của seller

Timestamp thiếu tạo variance null. Seller chỉ bị đánh dấu late handoff khi
handoff variance dương.

### 5.6 Policy handoff

PolicyAgent áp dụng primary issue theo thứ tự:

1. canceled_order_paid
2. unavailable_order_paid
3. late_delivery_seller
4. late_delivery_logistics
5. valid_split_payment
6. unsupported_late_claim

Sau đó agent thêm secondary issues theo thứ tự nghiệp vụ và trả về root cause,
responsible parties, refund cùng actions.

### 5.7 Verification handoff

VerifierAgent đọc lại CSV và kiểm tra:

- affected item, seller, payment IDs tồn tại;
- evidence đủ và đúng thứ tự;
- root cause khớp primary issue;
- item, freight, payment total khớp CSV;
- expected total, difference và reconciled đúng;
- refund đúng policy;
- case_status khớp refund;
- null handling và array limit hợp lệ.

Nếu một kiểm tra thất bại, case không được ghi output.

## 6. Evidence

Coordinator chỉ dựng năm dạng evidence được README cho phép:

    order:<order_id>
    item:<order_id>:<order_item_id>
    payment:<order_id>:<payment_sequential>
    seller:<seller_id>
    policy:<root_cause_code>

Seller evidence chỉ xuất hiện đối với seller chịu trách nhiệm.

## 7. Trace và audit

TraceLogger ghi một JSON object trên mỗi dòng với:

- timestamp và sequence;
- case_id;
- agent gửi và agent nhận;
- input references;
- output summary;
- model/provider cấu hình;
- execution mode.

Trace được reset ở đầu mỗi batch nên chỉ phản ánh lượt chạy mới nhất.
metadata.json ghi model, framework, runtime, policy version và số case.

## 8. Model và secret

Model được khai báo trong source tại src/config.py:

    MODEL_PROVIDER = "openrouter"
    MODEL_NAME = "google/gemma-3-4b-it"

OPENROUTER_API_KEY chỉ nằm trong .env. File .env bị .gitignore và không được đưa
vào trace, output, metadata hoặc submission ZIP.

Pipeline dùng data agent xác định để tạo ID, timestamp, số tiền và policy result.
LLMReviewAgent gọi OpenRouter một lần cho mỗi case để audit tính nhất quán của output
dự thảo; phản hồi LLM không tự thay đổi dữ liệu đã được đối chiếu từ CSV.
Gemma 3 4B có 4 tỷ tham số, đáp ứng giới hạn không quá 10B của bài thi.

## 9. Chạy và kiểm tra

    .\.venv\Scripts\python.exe -m src.run
    .\.venv\Scripts\python.exe -m src.validate_outputs

Kết quả hợp lệ gồm 50 output JSON, 350 trace event, 50 OpenRouter model call và
metadata khớp cấu hình trong source.
