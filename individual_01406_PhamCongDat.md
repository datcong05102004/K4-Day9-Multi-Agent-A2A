# Báo cáo cá nhân — Day 9: Multi-Agent A2A

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Phạm Công Đạt |
| MSSV | 2A202601406 |
| Khóa/Lớp | K4 |
| Vai trò chính | Thiết kế và triển khai toàn bộ pipeline multi-agent |
| Ngày hoàn thành | 2026-08-05 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

Bài được thực hiện cá nhân nên tôi chịu trách nhiệm cho toàn bộ source,
orchestration, kiểm tra và tài liệu.

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
|---|---|---|---|---|
| Cấu hình | src/config.py | .env và project root | Model, API key accessor, paths | Hoàn thành |
| Input validation | src/input_schema.py | EC_NNN.json | CaseInput | Hoàn thành |
| Data access | src/data_store.py | CSV Olist | Order/customer/item/payment/product rows | Hoàn thành |
| Customer analysis | src/agents/customer_agent.py | order_id | CustomerContext | Hoàn thành |
| Order/product analysis | src/agents/order_product_agent.py | order_id | OrderProductAnalysis | Hoàn thành |
| Payment analysis | src/agents/payment_agent.py | OrderProductAnalysis | PaymentAnalysis | Hoàn thành |
| Delivery analysis | src/agents/delivery_agent.py | OrderProductAnalysis | DeliveryAnalysis | Hoàn thành |
| Policy decision | src/agents/policy_agent.py | Các analysis handoff | PolicyDecision | Hoàn thành |
| LLM review | src/agents/llm_review_agent.py | CaseInput và CaseOutput | LLMReview | Hoàn thành |
| Orchestration | src/coordinator.py | CaseInput | CaseOutput dự thảo | Hoàn thành |
| Verification | src/verifier.py | CaseOutput và CSV | CaseOutput đã xác minh | Hoàn thành |
| Batch và audit | src/run.py, src/trace_logger.py, src/metadata.py | 50 input | Output, trace, metadata | Hoàn thành |
| Batch validation | src/validate_outputs.py | Output, trace, metadata | Báo cáo validation | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

Không có thành viên khác vì bài được thực hiện cá nhân. Tôi tự thực hiện việc
tích hợp module, kiểm tra contract và viết tài liệu kiến trúc.

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact | Kết quả bàn giao | Cách xác minh |
|---|---|---|---|
| Validate input | src/input_schema.py | Schema cho EC_001 đến EC_050 | Load từng file bằng Pydantic |
| Đối soát payment | PaymentAgent.reconcile | Tổng item, freight, payment và difference | Chạy EC_001 và EC_008 |
| Phân tích delivery | DeliveryAgent.analyze | Delivery và seller handoff variance | Chạy EC_001 và EC_002 |
| Áp dụng policy | PolicyAgent.apply | Issue, responsibility, refund, actions | Chạy sáu case đại diện |
| Tổng hợp output | CoordinatorAgent.process_case | CaseOutput đúng schema | Chạy EC_002 trong bộ nhớ |
| Xác minh output | VerifierAgent.verify | Từ chối ID, evidence hoặc refund sai | Thử thay refund thành 999 BRL |

Batch cuối đã sinh đủ 50 output từ EC_001.json đến EC_050.json. Trace có 350
event, tương ứng 7 handoff cho mỗi case. metadata.json ghi processed_cases bằng
50 và model_name là google/gemma-3-4b-it.

## 4. Giải thích phần kỹ thuật

### Vấn đề cần giải quyết

Một khiếu nại thương mại điện tử không thể được kết luận chỉ từ message của
khách hàng. Hệ thống phải đối chiếu order status, customer history, item,
seller, payment, product và delivery timestamp. Kết quả cuối phải xác định
issue, trách nhiệm, evidence, refund và actions theo EC_POLICY_V2.

### Cách triển khai

DataStore đọc các CSV cần thiết một lần và giữ ID dạng chuỗi. Coordinator nhận
CaseInput rồi gọi các agent chuyên trách. Mỗi agent chỉ xử lý một domain và trả
về Pydantic model:

1. CustomerAgent dùng customer_unique_id để tìm order lịch sử.
2. OrderProductAgent thu thập order, item, seller, product và category.
3. PaymentAgent cộng payment row và đối soát với item + freight.
4. DeliveryAgent tính delivery variance và handoff variance từng seller.
5. PolicyAgent áp dụng sáu nhánh theo đúng thứ tự ưu tiên.
6. Coordinator dựng affected entities, evidence và CaseOutput.
7. VerifierAgent đọc lại CSV để kiểm tra ID, số tiền và business invariant.

Payment được tính theo:

    expected_total_brl = sum(price) + sum(freight_value)
    difference_brl = sum(payment_value) - expected_total_brl
    reconciled = abs(difference_brl) <= 0.10

Delivery được tính theo:

    delivery_variance_hours =
        delivered_customer_date - estimated_delivery_date

    handoff_variance_hours =
        delivered_carrier_date - shipping_limit_date sớm nhất của seller

Tất cả số tiền và số giờ được làm tròn 2 chữ số. Timestamp thiếu tạo giá trị
null thay vì suy diễn.

### Input, output và contract

| Thành phần | Mô tả |
|---|---|
| Input | CaseInput từ input/EC_NNN.json |
| Output | CaseOutput theo mục 6 README |
| Module phụ thuộc | DataStore và các Pydantic handoff |
| Module sử dụng output | VerifierAgent, batch runner, validator |
| Điều kiện lỗi | Thiếu order, sai policy, evidence sai, refund sai, timestamp null, order không item |

### Cách xác minh

Các lệnh cần chạy cho batch cuối:

    .\.venv\Scripts\python.exe -m src.run
    .\.venv\Scripts\python.exe -m src.validate_outputs

- **Kết quả mong đợi:** 50 output JSON, 350 trace event và metadata khớp source.
- **Kết quả thực tế:** 50 output JSON, 350 trace event và metadata ghi 50 case.
  Batch validator hoàn tất không phát hiện lỗi.
- **Artifact:** output/, logging/trace.jsonl,
  logging/metadata.json.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Output chứa nhiều ID, timestamp và phép tính tiền; nếu để LLM
  tự sinh toàn bộ JSON thì có nguy cơ hallucination hoặc sai số.
- **Phương án đã cân nhắc:** dùng một prompt sinh toàn bộ output; hoặc tách các
  data agent có contract và dùng code xác định cho phép tính.
- **Phương án đã chọn:** agent chuyên trách, Pydantic handoff và verifier độc
  lập dựa trên CSV.
- **Lý do:** tăng correctness, reproducibility và khả năng audit; đồng thời thể
  hiện phân công và handoff thực thay vì chỉ đặt nhiều tên agent.
- **Bằng chứng:** Verifier có thể từ chối refund bị sửa thành 999 BRL và kiểm
  tra lại affected ID/evidence từ dữ liệu nguồn.

Model được cấu hình trong source là google/gemma-3-4b-it và được gọi qua
OpenRouter. Gemma 3 4B có 4 tỷ tham số, đáp ứng giới hạn không quá 10B.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Phần 7 của template hỏi về Crossref, vector index,
  retrieval quality và freshness monitoring.
- **Bước tái hiện:** mở template báo cáo cá nhân được cung cấp trong repo.
- **Nguyên nhân gốc:** nội dung template bị giữ lại từ một bài lab khác.
- **Cách xử lý:** thay phần này bằng giải thích luồng Olist end-to-end.
- **Cách xác minh:** các module, artifact và thuật ngữ trong báo cáo đều thuộc
  bài Multi-Agent E-commerce Dispute Resolution.
- **Điều học được:** template cần được đối chiếu với README trước khi điền,
  không sao chép nguyên nội dung không liên quan.

Blocker batch đã được xử lý bằng cách chạy lại src.run và
src.validate_outputs. Kết quả được đối chiếu bằng số file output, số dòng trace
và processed_cases trong metadata.

## 7. Hiểu biết về luồng end-to-end

Một case bắt đầu từ claimed_order_id trong input JSON. Coordinator giao ID này
cho CustomerAgent và OrderProductAgent. CustomerAgent xác định khách hàng bằng
customer_unique_id và tìm lịch sử. OrderProductAgent lấy order, item, seller,
product và category. PaymentAgent dùng item handoff để đối soát tổng payment
với item + freight. DeliveryAgent dùng timestamp trong order và hạn giao của
item để xác định giao trễ và seller handoff trễ.

PolicyAgent nhận các analysis handoff và áp dụng EC_POLICY_V2 theo thứ tự ưu
tiên. Coordinator dùng kết luận này để dựng affected entities, customer/product
context, root cause, evidence, refund và actions. VerifierAgent đọc lại CSV và
chỉ chấp nhận output khi ID, evidence, phép tính, null handling và giới hạn
schema đều đúng. Batch runner ghi output sau verification, tạo sáu trace event
mỗi case và ghi metadata cho lượt chạy mới nhất. Validator đọc lại toàn bộ
artifact trước khi đóng gói.

Một lượt chạy chỉ được xem là thành công khi:

1. Có đúng 50 JSON từ EC_001 đến EC_050.
2. Cả 50 output qua Pydantic và Verifier.
3. Trace có đúng 350 event, mỗi case 7 event.
4. metadata khớp model và runtime trong source.
5. ZIP chỉ chứa 50 JSON của output.

## 8. Cam kết

- [x] Nội dung báo cáo phản ánh đúng phần việc và trạng thái hiện tại.
- [x] Tôi có thể giải thích luồng end-to-end.
- [x] Tôi không ghi đã chạy thành công cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa .env, API key, token hoặc secret.
- [x] Báo cáo không sao chép báo cáo của thành viên khác.

**Họ và tên:** Phạm Công Đạt

**Ngày xác nhận:** 2026-08-05
