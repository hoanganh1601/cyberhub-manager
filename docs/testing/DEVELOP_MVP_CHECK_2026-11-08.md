# Đối chiếu develop với các task MVP — 08/11/2026

## Kết luận

`develop` tại `2424c12` đã có các chức năng P0 chính và toàn bộ 970 unit/UI/HTTP
tests hiện tại chạy thành công trên máy Windows này. Chưa đủ căn cứ chuyển toàn bộ
task sang Done theo Definition of Done trong `docs/04_LINEAR_BACKLOG.md`:

- Còn sai lệch ngôn ngữ VI ở thông báo lỗi và một số hộp xác nhận.
- Checklist AC-01…AC-24 chưa điền kết quả, người thực hiện và evidence.
- Chưa xác minh lại integration MySQL trong lượt kiểm tra này do môi trường DB.
- Chưa có bằng chứng video demo và nghiệm thu máy Windows sạch/DPI đầy đủ.

Đây là báo cáo kiểm tra, không phải chữ ký nghiệm thu và không thay đổi trạng thái
Linear hay các PR.

## Snapshot và phạm vi

- Repo: `hoanganh1601/cyberhub-manager`.
- Đã fetch lại `origin/develop`; HEAD và remote cùng `2424c12`.
- PR tích hợp mới nhất: [#31](https://github.com/hoanganh1601/cyberhub-manager/pull/31).
- Đối chiếu: requirements P0, backlog HA/LI/NG, Definition of Done, checklist manual,
  mã nguồn, lịch sử PR và báo cáo release đã lưu trong repo.
- Không sửa source, merge/đóng PR, hoặc thay đổi cấu hình/database ứng dụng.

## Chức năng cơ bản hiện có

| Nhóm | Implementation trên develop | Phần nghiệm thu cần lưu ý |
|---|---|---|
| HA-01…HA-08, HA-10 | Skeleton, schema/migration/seed, pool/transaction, repositories, ERD/data dictionary | DB integration và dictionary đối chiếu DB chưa chạy lại được trong lượt này |
| HA-09 | Script benchmark/EXPLAIN, hướng dẫn setup và đóng gói; build wheel thành công tại máy này | Cần nghiệm thu chạy trên Windows sạch, DPI và môi trường đích |
| HA-11 | Login thật/mock, validation, busy state, chuyển Login ↔ AppShell, actor và logout | Cần review UI/acceptance của nhóm |
| LI-01…LI-08, LI-10 | Domain/DTO/contracts/mock; auth/customer/wallet/machine/session/checkout/report; mapping lỗi và retry deadlock | Unit hiện tại pass; kết quả DB thật của lượt release trước được lưu riêng |
| LI-09 | Có unit/integration suite, guard DB test và checklist AC-01…24 | Automated unit đạt; manual chưa có kết quả ký xác nhận |
| NG-01…NG-07 | Theme/component, điều hướng theo role, dashboard/máy, khách/nạp tiền, mở phiên, checkout/receipt, hóa đơn/doanh thu/biểu đồ | Có các view thật cho đủ 5 menu; vẫn cần nghiệm thu trực quan/DB thật |
| NG-08 | Error/loading/empty, keyboard và EN đã có implementation/tests | AC-24 chưa đạt hoàn toàn ở VI; manual sweep chưa ký |
| NG-09 | Có script demo và screenshot | Tài liệu vẫn ghi chưa có video demo; cần quay và gắn evidence |

Các luồng P0 tương ứng đã có: đăng nhập/phân quyền; tạo/sửa/tìm/khóa khách;
nạp tiền/lịch sử; quản lý máy/bảo trì/archive; preview/mở phiên và chặn trùng;
ước tính thời lượng/số dư; checkout đủ số dư hoặc bù thiếu; receipt/hóa đơn;
doanh thu từ hóa đơn PAID; transaction/rollback và lỗi an toàn.

Khuyến mãi tự động, quản lý nhiều cơ sở đầy đủ, quản lý nhân viên, khách tự đăng nhập
và xuất/in hóa đơn được xếp P1 trong requirements. Thanh toán qua cổng ngân hàng
thật nằm ngoài phạm vi; QR hiện tại chỉ minh họa và xác nhận thủ công.

## Kết quả thực sự chạy trong lượt này

| Kiểm tra | Kết quả |
|---|---|
| `python -m pytest tests/unit -q` | **970 passed**, 167,20 giây; 0 failure/error/skip |
| `python -m compileall -q src scripts tests` | Pass |
| `python -m pip check` | Không có dependency lỗi |
| Build wheel với build isolation mặc định | Pass; `cyberhub_manager-0.1.0-py3-none-any.whl` |
| Kiểm tra nội dung wheel | Có 4 TTF, 1 logo PNG, 2 web static assets, 1 web template |
| Đếm checklist manual | 24 ca; 24 kết quả thực tế trống; 24 trạng thái vẫn là mẫu `PASS / FAIL` |
| Probe widget thật, context `vi` | Xác nhận lỗi nhập liệu và dialog khóa vẫn hiện tiếng Anh |
| Kết nối DB test theo cấu hình hiện tại | Không kết nối được `127.0.0.1:3307` |
| Thăm dò MySQL native ở 3306 bằng credential cấu hình hiện tại | Bị từ chối xác thực; không sửa credential/cấu hình |
| `scripts/gen_data_dictionary.py --check` | Chưa xác minh được vì cần kết nối DB |

Lượt build đầu thử `--no-build-isolation` không thực hiện được vì venv không có
setuptools. Lượt build theo cấu hình mặc định đã tải build dependencies trong
môi trường tạm và thành công; đây không phải lỗi package của repo.

Không chạy 194 integration tests trong điều kiện DB chưa sẵn sàng và không đánh
dấu chúng PASS. Báo cáo `HA_LI_NG_RELEASE_AUDIT.md` cùng log
`evidence/pytest-release-linux.txt` ghi **1.164 passed = 970 unit + 194 integration**
trên Linux/MySQL 8.4.13 ở lượt release trước. Kết quả lịch sử này được phân biệt
với 970 test vừa chạy lại trên Windows.

JUnit lượt này được lưu ngoài repo tại
`%TEMP%\cyberhub-workspace-validation\develop-mvp-unit.xml`;
wheel tại `%TEMP%\cyberhub-mvp-wheel\`.

## Sai lệch cần xử lý: AC-24 / ngôn ngữ VI

`docs/03_UI_THEME.md` yêu cầu nhãn, toast, dialog, trạng thái và lỗi từng trường
đều theo lựa chọn VI/EN. Probe với `ViewContext.language == "vi"` cho kết quả:

| Nội dung | Kết quả thực tế |
|---|---|
| Tiêu đề tạo khách | `Tạo khách hàng` |
| Lỗi tên trống | `This field is required.` |
| Tiêu đề dialog khóa | `Lock customer account` |
| Nút hủy dialog khóa | `Cancel` |

Nguồn liên quan:

- `ui/messages.py`: constants và field errors chỉ tiếng Anh.
- `ui/dialogs/customer_dialog.py`: đưa kết quả validation thẳng vào field.
- `ui/dialogs/customer_lock_dialog.py`: title/subtitle/confirm/effects tiếng Anh cố định.
- `ui/app_shell.py`: xác nhận đăng xuất dùng các constants tiếng Anh cố định.

Vì vậy test hiện tại xanh không đủ chứng minh AC-24 đã đạt ở VI. Cần đồng bộ cả
feedback/validation/confirmation, rồi bổ sung kiểm tra VI cho các nhánh này.

## Năm PR UI đang mở

| PR | Task được ghi trên PR | Trạng thái quan sát |
|---|---|---|
| [#17](https://github.com/hoanganh1601/cyberhub-manager/pull/17) | NG-06 checkout/receipt | Open; chưa merge |
| [#18](https://github.com/hoanganh1601/cyberhub-manager/pull/18) | NG-07 reports/login | Open; chưa merge |
| [#19](https://github.com/hoanganh1601/cyberhub-manager/pull/19) | NG-08 integration sweep | Open; chưa merge |
| [#20](https://github.com/hoanganh1601/cyberhub-manager/pull/20) | NG-04 customers/top-up | Open; chưa merge |
| [#21](https://github.com/hoanganh1601/cyberhub-manager/pull/21) | NG-05 open session | Open; chưa merge |

Đã fetch head của cả 5 PR để đối chiếu. Head của #17, #18, #20 và #21 đều là
ancestor của head #19: đây là các nhánh chồng lấp, không phải năm bộ thay đổi độc lập.
Head #19 còn 14 commit không nằm trong lịch sử develop; develop cũng có 25 commit
không nằm trong nhánh đó. Không thể coi các PR này đã merge chỉ vì cùng tên chức năng.

Các chức năng tương ứng đã có implementation khác trên develop qua các đợt tích hợp
UI trước đó và phần nâng cấp hiện tại. Cần review phần khác biệt trước khi quyết
định lấy thêm hoặc đóng PR trùng; không cần merge toàn bộ để có các luồng P0 kể trên.

## Thứ tự hoàn tất để chốt MVP

1. Đồng bộ wording VI cho validation/feedback/dialog và kiểm tra lại AC-24.
2. Chuẩn bị MySQL test theo README, chạy lại toàn bộ suite gồm integration và
   kiểm tra data dictionary/benchmark theo phạm vi cần nghiệm thu.
3. Thực hiện AC-01…24 trên desktop Windows với DB demo riêng; ghi người/ngày/kết quả/evidence,
   gồm hai cửa sổ cùng DB, mất/kết nối lại DB, DPI 100/125/150% và phím tắt.
4. Xác nhận setup trên máy sạch, quay video/rehearsal NG-09 và lấy review của nhóm.
5. Đối chiếu/giải quyết trạng thái các PR cũ và cập nhật Linear theo bằng chứng thật.
