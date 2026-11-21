# -*- coding: utf-8 -*-
import os, sys, re

def escape_latex(s):
    if not s:
        return ''
    s = s.replace('\\', '\\textbackslash{}')
    s = s.replace('&', '\\&')
    s = s.replace('%', '\\%')
    s = s.replace('$', '\\$')
    s = s.replace('#', '\\#')
    s = s.replace('_', '\\_')
    s = s.replace('{', '\\{')
    s = s.replace('}', '\\}')
    s = s.replace('~', '\\textasciitilde{}')
    s = s.replace('^', '\\textasciicircum{}')
    s = s.replace('→', '$\\rightarrow$')
    s = s.replace('×', '$\\times$')
    s = s.replace('–', '--')
    s = s.replace('—', '---')
    return s

def escape_code(s):
    if not s:
        return ''
    return s.replace('_', '\\_')

with open('docs/diagrams/data_dictionary.md', encoding='utf-8') as f:
    text = f.read()

backtick = chr(96)
sec3 = text[text.find('## 3.'):]
sections = re.split(r'\n###\s+', sec3)

parsed_tables = {}
for s in sections[1:]:
    lines = s.strip().split('\n')
    tname = lines[0].strip()
    
    desc_lines = []
    i = 1
    while i < len(lines) and not lines[i].strip().startswith('| Cột |'):
        if lines[i].strip():
            desc_lines.append(lines[i].strip())
        i += 1
    meaning = ' '.join(desc_lines)
    
    cols = []
    i += 2
    while i < len(lines) and lines[i].strip().startswith('|'):
        parts = lines[i].strip().split('|')
        if len(parts) >= 7:
            cname = parts[1].strip().replace(backtick, '')
            ctype = parts[2].strip().replace(backtick, '')
            cnull = parts[3].strip()
            cdef = parts[4].strip()
            ckey = parts[5].strip()
            cmean = parts[6].strip()
            cols.append((cname, ctype, cnull, cdef, ckey, cmean))
        i += 1
    
    rules = []
    while i < len(lines):
        line = lines[i].strip()
        if line and not line.startswith('###') and not line.startswith('##'):
            rules.append(line)
        i += 1
    
    parsed_tables[tname] = {
        'meaning': meaning,
        'cols': cols,
        'rules': rules
    }

domains = [
    {
        'title': 'Phân hệ Quản trị cơ sở, Nhân sự và Kiểm toán',
        'tables': [
            ('stores', 'STORES', 'Đạt', 'Mô tả cơ sở phụ thuộc trực tiếp vào khóa chính id.'),
            ('employees', 'EMPLOYEES', 'Đạt', 'Tách cơ sở qua store_id, không lặp thuộc tính mô tả cửa hàng.'),
            ('employee_profiles', 'EMPLOYEE_PROFILES', 'Đạt', 'Tách hồ sơ nhân sự khỏi bảng xác thực, khóa ứng viên code và employee_id.'),
            ('employee_store_assignments', 'EMPLOYEE_STORE_ASSIGNMENTS', 'Đạt', 'Bảng liên kết N:M có khóa ghép (employee_id, store_id), đạt 3NF.'),
            ('management_audit', 'MANAGEMENT_AUDIT', 'Đạt', 'Sổ nhật ký kiểm toán bất biến chỉ thêm, thuộc tính phụ thuộc vào khóa id.')
        ]
    },
    {
        'title': 'Phân hệ Khách hàng, Hội viên và An ninh tài khoản',
        'tables': [
            ('customers', 'CUSTOMERS', 'Đạt', 'Hồ sơ cá nhân độc lập với số dư ví và tài khoản đăng nhập.'),
            ('customer_store_links', 'CUSTOMER_STORE_LINKS', 'Đạt', 'Bảng liên kết N:M giữa khách hàng và cơ sở với khóa ghép.'),
            ('accounts', 'ACCOUNTS', 'Đạt', 'Tách hồ sơ khách hàng và sổ cái giao dịch, đạt 3NF chuẩn tắc.'),
            ('customer_avatars', 'CUSTOMER_AVATARS', 'Đạt', 'Tách dữ liệu media WebP khỏi tài khoản, khóa chính id kiêm FK.'),
            ('customer_notification_reads', 'CUSTOMER_NOTIFICATION_READS', 'Đạt', 'Khóa ghép (account_id, event_id), thuộc tính phụ thuộc toàn bộ khóa.'),
            ('customer_notification_events', 'CUSTOMER_NOTIFICATION_EVENTS', 'Đạt', 'Sổ sự kiện thông báo bất biến, chống phát trùng bằng khóa nghiệp vụ.'),
            ('customer_email_tokens', 'CUSTOMER_EMAIL_TOKENS', 'Đạt', 'Lưu token đã băm HMAC, phụ thuộc trực tiếp vào khóa chính.'),
            ('customer_mail_outbox', 'CUSTOMER_MAIL_OUTBOX', 'Đạt', 'Bảng hàng đợi gửi thư, các thuộc tính mô tả phụ thuộc vào id.'),
            ('customer_security_audit', 'CUSTOMER_SECURITY_AUDIT', 'Đạt', 'Nhật ký kiểm toán an ninh bất biến, chỉ ghi và không sửa đổi.')
        ]
    },
    {
        'title': 'Phân hệ Máy trạm, Phòng máy và Quản lý sự cố',
        'tables': [
            ('machines', 'MACHINES', 'Đạt', 'Không lặp mô tả cửa hàng; giá phiên là snapshot riêng tại phiên.'),
            ('machine_room_types', 'MACHINE_ROOM_TYPES', 'Đạt', 'Phân loại phòng máy, khóa chính machine_id kiêm FK tham chiếu.'),
            ('usage_sessions', 'USAGE_SESSIONS', 'Đạt', 'Tham chiếu khách, máy, nhân viên bằng FK; snapshot hourly_rate hợp lệ.'),
            ('machine_incidents', 'MACHINE_INCIDENTS', 'Đạt', 'Phiếu sự cố gắn với máy trạm và nhân viên phụ trách, đạt 3NF.'),
            ('machine_incident_parts', 'MACHINE_INCIDENT_PARTS', 'Đạt', 'Linh kiện sử dụng cho phiếu sự cố, phụ thuộc trực tiếp vào khóa id.'),
            ('machine_incident_events', 'MACHINE_INCIDENT_EVENTS', 'Đạt', 'Lịch sử chuyển trạng thái sự cố, sổ sự kiện chỉ thêm.')
        ]
    },
    {
        'title': 'Phân hệ Giao dịch, Hóa đơn và Ca làm việc tiền mặt',
        'tables': [
            ('account_transactions', 'ACCOUNT_TRANSACTIONS', 'Đạt', 'Mỗi dòng biểu diễn một sự kiện biến động số dư bất biến.'),
            ('invoices', 'INVOICES', 'Có snapshot', 'Lưu bối cảnh khách/nhân viên/cửa hàng phục vụ kiểm toán (phi chuẩn hóa có kiểm soát).'),
            ('cash_shifts', 'CASH_SHIFTS', 'Đạt', 'Ca làm việc của nhân viên tại cơ sở, các chỉ số két phụ thuộc vào ca.'),
            ('cash_shift_entries', 'CASH_SHIFT_ENTRIES', 'Đạt', 'Bút toán chi tiết sổ quỹ ca tiền mặt, phụ thuộc vào khóa chính id.')
        ]
    },
    {
        'title': 'Phân hệ Thực đơn và Bán hàng POS',
        'tables': [
            ('menu_categories', 'MENU_CATEGORIES', 'Đạt', 'Danh mục thực đơn theo cơ sở, đạt 3NF.'),
            ('menu_items', 'MENU_ITEMS', 'Đạt', 'Món ăn thuộc danh mục, không lưu lặp mô tả danh mục.'),
            ('menu_item_images', 'MENU_ITEM_IMAGES', 'Đạt', 'Tách media ảnh món độc lập, khóa chính item_id kiêm FK.'),
            ('menu_item_changes', 'MENU_ITEM_CHANGES', 'Đạt', 'Sổ lịch sử điều chỉnh giá và thông tin món, chỉ thêm.'),
            ('menu_orders', 'MENU_ORDERS', 'Đạt', 'Đơn đặt món POS gắn với phiên và máy, đạt 3NF.'),
            ('menu_order_items', 'MENU_ORDER_ITEMS', 'Có snapshot', 'Lưu snapshot item_name và unit_price lúc đặt để bảo toàn lịch sử.'),
            ('menu_order_pricing', 'MENU_ORDER_PRICING', 'Có snapshot', 'Snapshot kết quả tính giá chiết khấu bất biến tại thời điểm chốt đơn.'),
            ('menu_promotions', 'MENU_PROMOTIONS', 'Đạt', 'Chính sách khuyến mãi POS, các điều kiện phụ thuộc vào khóa id.'),
            ('pos_order_reversals', 'POS_ORDER_REVERSALS', 'Đạt', 'Yêu cầu hoàn hủy đơn POS với quy trình Maker-Checker, đạt 3NF.'),
            ('menu_order_recipe_snapshots', 'MENU_ORDER_RECIPE_SNAPSHOTS', 'Có snapshot', 'Snapshot định mức nguyên liệu lúc đặt để đổi công thức không làm sai xuất kho cũ.')
        ]
    },
    {
        'title': 'Phân hệ Quản lý kho nguyên liệu và Định lượng',
        'tables': [
            ('inventory_ingredients', 'INVENTORY_INGREDIENTS', 'Đạt', 'Nguyên liệu quản lý theo từng cơ sở, đạt 3NF.'),
            ('menu_item_recipes', 'MENU_ITEM_RECIPES', 'Đạt', 'Bảng quan hệ N:M giữa món và nguyên liệu, khóa ghép (item_id, ingredient_id).'),
            ('inventory_movements', 'INVENTORY_MOVEMENTS', 'Đạt', 'Sổ cái kho bất biến ghi nhận mọi biến động xuất nhập tồn.'),
            ('inventory_counts', 'INVENTORY_COUNTS', 'Đạt', 'Phiếu kiểm kê đề xuất điều chỉnh kho, đạt 3NF.')
        ]
    },
    {
        'title': 'Phân hệ Khuyến mãi nạp tiền, Voucher và Tích điểm',
        'tables': [
            ('promotions', 'PROMOTIONS', 'Đạt', 'Chính sách thưởng nạp tiền, phụ thuộc vào khóa chính id.'),
            ('loyalty_settings', 'LOYALTY_SETTINGS', 'Đạt', 'Bảng cấu hình hệ thống duy nhất id=1 có version chống ghi đè.'),
            ('reward_catalog', 'REWARD_CATALOG', 'Đạt', 'Danh mục phần thưởng độc lập, đạt 3NF.'),
            ('customer_vouchers', 'CUSTOMER_VOUCHERS', 'Có snapshot', 'Lưu snapshot điều kiện áp dụng lúc phát hành voucher.'),
            ('voucher_events', 'VOUCHER_EVENTS', 'Đạt', 'Nhật ký sự kiện vòng đời voucher, chỉ thêm.'),
            ('loyalty_point_grants', 'LOYALTY_POINT_GRANTS', 'Đạt', 'Bản ghi cộng điểm thưởng hội viên từ voucher, đạt 3NF.')
        ]
    },
    {
        'title': 'Phân hệ Trò chơi giải trí và Vòng quay may mắn',
        'tables': [
            ('games', 'GAMES', 'Đạt', 'Cấu hình trò chơi chung toàn hệ thống, đạt 3NF.'),
            ('game_prizes', 'GAME_PRIZES', 'Đạt', 'Ô thưởng gắn với game_id, xác suất và phần thưởng phụ thuộc vào id.'),
            ('game_wallets', 'GAME_WALLETS', 'Đạt', 'Ví xu trò chơi riêng biệt, tách độc lập khỏi ví tiền mặt.'),
            ('game_sessions', 'GAME_SESSIONS', 'Đạt', 'Lịch sử lượt quay máy chủ bốc thăm và chụp lại kết quả.'),
            ('game_coin_ledger', 'GAME_COIN_LEDGER', 'Đạt', 'Sổ cái biến động số dư xu, bất biến chỉ thêm.')
        ]
    },
    {
        'title': 'Phân hệ Quảng cáo nhận thưởng',
        'tables': [
            ('ad_settings', 'AD_SETTINGS', 'Đạt', 'Cấu hình chương trình quảng cáo, một dòng duy nhất id=1.'),
            ('ad_creatives', 'AD_CREATIVES', 'Đạt', 'Nội dung quảng cáo nội bộ, đạt 3NF.'),
            ('ad_reward_events', 'AD_REWARD_EVENTS', 'Đạt', 'Sự kiện xem quảng cáo với token dùng một lần, đạt 3NF.')
        ]
    },
    {
        'title': 'Phân hệ Mua sắm, Nhập kho và Công nợ nhà cung cấp',
        'tables': [
            ('suppliers', 'SUPPLIERS', 'Đạt', 'Nhà cung cấp quản lý theo cơ sở, đạt 3NF.'),
            ('purchase_requests', 'PURCHASE_REQUESTS', 'Đạt', 'Đề nghị mua sắm nguyên vật liệu có người lập và người duyệt.'),
            ('purchase_request_lines', 'PURCHASE_REQUEST_LINES', 'Đạt', 'Chi tiết đề nghị mua sắm, khóa ghép (request_id, ingredient_id).'),
            ('purchase_orders', 'PURCHASE_ORDERS', 'Đạt', 'Đơn đặt mua hàng tạo từ đề nghị đã duyệt, đạt 3NF.'),
            ('purchase_order_lines', 'PURCHASE_ORDER_LINES', 'Đạt', 'Chi tiết đơn đặt mua hàng, khóa ghép (order_id, ingredient_id).'),
            ('goods_receipts', 'GOODS_RECEIPTS', 'Đạt', 'Phiếu nhận hàng thực tế, tự động tạo nhập kho và công nợ.'),
            ('goods_receipt_lines', 'GOODS_RECEIPT_LINES', 'Đạt', 'Chi tiết hàng đạt, hỏng, thiếu trong phiếu nhận hàng.'),
            ('supplier_payables', 'SUPPLIER_PAYABLES', 'Đạt', 'Khoản công nợ phải trả gắn với phiếu nhận hàng, đạt 3NF.'),
            ('supplier_payable_approvals', 'SUPPLIER_PAYABLE_APPROVALS', 'Đạt', 'Bản ghi phê duyệt công nợ theo chính sách phân tách quyền Maker-Checker.')
        ]
    },
    {
        'title': 'Phân hệ Đối tác thương mại và Phân phối dịch vụ',
        'tables': [
            ('commercial_partners', 'COMMERCIAL_PARTNERS', 'Đạt', 'Đối tác thương mại bên ngoài, đạt 3NF.'),
            ('commercial_contracts', 'COMMERCIAL_CONTRACTS', 'Đạt', 'Hợp đồng thương mại có phê duyệt hai bước, đạt 3NF.'),
            ('commercial_campaigns', 'COMMERCIAL_CAMPAIGNS', 'Đạt', 'Chiến dịch thương mại gắn với hợp đồng, đạt 3NF.'),
            ('commercial_placements', 'COMMERCIAL_PLACEMENTS', 'Đạt', 'Vị trí phân phối nội dung đối tác, đạt 3NF.'),
            ('commercial_play_sessions', 'COMMERCIAL_PLAY_SESSIONS', 'Đạt', 'Phiên chơi dịch vụ đối tác với mã token một lần.'),
            ('commercial_events', 'COMMERCIAL_EVENTS', 'Đạt', 'Sổ sự kiện tương tác thương mại bất biến, chống ghi trùng.'),
            ('commercial_reward_grants', 'COMMERCIAL_REWARD_GRANTS', 'Đạt', 'Hàng đợi trả thưởng thương mại bất đồng bộ, đạt 3NF.'),
            ('commercial_settlements', 'COMMERCIAL_SETTLEMENTS', 'Đạt', 'Kỳ đối soát quyết toán doanh thu với đối tác, đạt 3NF.'),
            ('commercial_settlement_lines', 'COMMERCIAL_SETTLEMENT_LINES', 'Đạt', 'Chi tiết doanh thu và sản lượng từng vị trí trong kỳ đối soát.')
        ]
    }
]

c4_lines = []
c4_lines.append('\\chapter{Chuẩn hóa các lược đồ quan hệ về dạng chuẩn 3NF}')
c4_lines.append('')
c4_lines.append('\\section{Mục tiêu và phương pháp phân tích}')
c4_lines.append('Chuẩn hóa cơ sở dữ liệu là quá trình tổ chức các thuộc tính và bảng quan hệ nhằm tối thiểu hóa sự dư thừa dữ liệu, loại trừ các bất thường khi thao tác (thêm, sửa, xóa) và đảm bảo tính nhất quán logic cao nhất. Chương này trình bày phân tích chuẩn hóa toàn diện cho toàn bộ 70 bảng cơ sở dữ liệu của CyberHub Manager dựa trên lý thuyết phụ thuộc hàm và khóa ứng viên.\\par')
c4_lines.append('')
c4_lines.append('Quy trình phân tích gồm: thẩm định dạng chuẩn 1NF (tính nguyên tử), 2NF (loại bỏ phụ thuộc bộ phận vào khóa ghép), và 3NF (loại bỏ phụ thuộc bắc cầu qua thuộc tính không khóa). Đồng thời, chương này phân tích sâu sắc các quyết định phi chuẩn hóa có kiểm soát (Controlled Denormalization) đối với các trường snapshot bối cảnh lịch sử phục vụ kiểm toán tài chính và đối soát.\\par')
c4_lines.append('')
c4_lines.append('\\section{Cơ sở lý thuyết chuẩn hóa}')
c4_lines.append('\\subsection{Phụ thuộc hàm và khóa}')
c4_lines.append('Cho quan hệ $R$ và hai tập thuộc tính $X, Y \\subseteq R$. Phụ thuộc hàm $X \\rightarrow Y$ phát biểu rằng với mọi cặp bộ giá trị $t_1, t_2 \\in R$, nếu $t_1[X] = t_2[X]$ thì bắt buộc $t_1[Y] = t_2[Y]$. Một tập thuộc tính $K$ là siêu khóa nếu $K \\rightarrow R$. $K$ là khóa ứng viên nếu $K$ là siêu khóa tối thiểu (không tồn tại tập con thực sự $K\' \\subset K$ sao cho $K\' \\rightarrow R$). Khóa chính (PK) là khóa ứng viên được chọn để định danh dòng dữ liệu.\\par')
c4_lines.append('')
c4_lines.append('\\subsection{Dạng chuẩn thứ nhất (1NF)}')
c4_lines.append('Một quan hệ đạt 1NF khi và chỉ khi mọi thuộc tính chỉ chứa các giá trị nguyên tử (atomic values) thuộc miền xác định, không chứa các tập hợp, mảng lặp hoặc danh sách phức hợp trong một cột. Trong CyberHub Manager, mọi thuộc tính đa trị đều được tách thành các bảng dòng chi tiết riêng biệt (ví dụ món trong đơn đặt thành \\texttt{MENU\\_ORDER\\_ITEMS}, nguyên liệu mua thành \\texttt{PURCHASE\\_ORDER\\_LINES}).\\par')
c4_lines.append('')
c4_lines.append('\\subsection{Dạng chuẩn thứ hai (2NF)}')
c4_lines.append('Một quan hệ đạt 2NF khi và chỉ khi nó đạt 1NF và mọi thuộc tính không khóa đều phụ thuộc đầy đủ vào toàn bộ khóa chính, không phụ thuộc vào bất kỳ bộ phận thực sự nào của khóa chính ghép. Với các bảng có khóa chính đơn (như \\texttt{id}), quan hệ mặc nhiên thỏa mãn 2NF. Với các bảng sử dụng khóa ghép (như \\texttt{MENU\\_ITEM\\_RECIPES(item\\_id, ingredient\\_id)}), mọi thuộc tính không khóa như \\texttt{quantity} đều phụ thuộc đồng thời vào cả hai thành phần của khóa.\\par')
c4_lines.append('')
c4_lines.append('\\subsection{Dạng chuẩn thứ ba (3NF)}')
c4_lines.append('Một quan hệ đạt 3NF khi và chỉ khi nó đạt 2NF và với mọi phụ thuộc hàm không tầm thường $X \\rightarrow A$, hoặc $X$ là một siêu khóa, hoặc $A$ là một thuộc tính khóa (thuộc một khóa ứng viên nào đó). Nói cách khác, không tồn tại phụ thuộc bắc cầu giữa các thuộc tính không khóa.\\par')
c4_lines.append('')
c4_lines.append('\\section{Phân tích chuẩn hóa 70 bảng theo từng phân hệ}')
c4_lines.append('Dưới đây là kết quả phân tích chuẩn hóa chi tiết cho toàn bộ 70 bảng theo 11 phân hệ chức năng. Đối với từng bảng, báo cáo chỉ rõ khóa ứng viên, phụ thuộc hàm chủ đạo và mức độ thỏa mãn dạng chuẩn 3NF:\\par')
c4_lines.append('')

for d_idx, domain in enumerate(domains, 1):
    dtitle = domain['title']
    c4_lines.append(f'\\subsection{{{dtitle}}}')
    
    for tname, rel_name, nf_status, reason in domain['tables']:
        p = parsed_tables.get(tname, {})
        cols = p.get('cols', [])
        
        pk_cols = [c[0] for c in cols if 'PK' in c[4]]
        uqs = [c[0] for c in cols if ('UK' in c[4] or 'UQ' in c[4]) and 'PK' not in c[4]]
        
        candidate_keys = [f"\\texttt{{{escape_code(', '.join(pk_cols))}}}"]
        for u in uqs:
            candidate_keys.append(f"\\texttt{{{escape_code(u)}}}")
        
        c4_lines.append(f'\\subsubsection{{{rel_name} -- \\texttt{{{escape_code(tname)}}}}}')
        c4_lines.append('\\begin{itemize}')
        c4_lines.append(f'  \\item \\textbf{{Khóa ứng viên:}} {", ".join(candidate_keys)}.')
        c4_lines.append(f'  \\item \\textbf{{Đánh giá dạng chuẩn:}} \\textbf{{{nf_status}}}.')
        c4_lines.append(f'  \\item \\textbf{{Cơ sở lý giải:}} {reason}')
        c4_lines.append('\\end{itemize}')
        c4_lines.append('')

c4_lines.append('\\section{Đánh giá các trường hợp phi chuẩn hóa có kiểm soát}')
c4_lines.append('Trong các hệ thống phần mềm nghiệp vụ thực tế, việc tuân thủ 3NF một cách máy móc có thể dẫn đến việc phá vỡ tính toàn vẹn dữ liệu lịch sử tài chính hoặc làm suy giảm nghiêm trọng hiệu năng truy vấn. CyberHub Manager đã đưa ra các quyết định phi chuẩn hóa có kiểm soát (Controlled Denormalization) tại một số vị trí then chốt:\\par')
c4_lines.append('')
c4_lines.append('\\begin{itemize}')
c4_lines.append('  \\item \\textbf{Snapshot bối cảnh tại \\texttt{INVOICES}:} Hóa đơn lưu trữ trực tiếp \\texttt{customer\\_id}, \\texttt{employee\\_id}, và \\texttt{store\\_id} dù các thông tin này có thể suy diễn từ \\texttt{usage\\_sessions}. Lý do: Nếu nhân viên checkout sau này chuyển công tác sang cơ sở khác hoặc bị thay đổi trạng thái, việc tra cứu ngược qua phiên có thể dẫn đến báo cáo lịch sử sai lệch so với thời điểm phát hành hóa đơn thực tế. Snapshot này được tạo cùng transaction checkout và là bất biến (không cho phép sửa).\\par')
c4_lines.append('  \\item \\textbf{Snapshot tên và đơn giá tại \\texttt{MENU\\_ORDER\\_ITEMS}:} Mỗi dòng gọi món lưu trực tiếp \\texttt{item\\_name} và \\texttt{unit\\_price} tại thời điểm đặt. Lý do: Khi quán net cập nhật giá món hoặc đổi tên sản phẩm trong danh mục \\texttt{MENU\\_ITEMS}, các hóa đơn và đơn đặt cũ tuyệt đối không được phép bị thay đổi số tiền lịch sử.\\par')
c4_lines.append('  \\item \\textbf{Snapshot định mức nguyên liệu tại \\texttt{MENU\\_ORDER\\_RECIPE\\_SNAPSHOTS}:} Lưu trữ công thức pha chế/nấu ăn tại thời điểm khách đặt hàng. Nhờ đó, việc bếp trưởng điều chỉnh công thức món ăn sau này sẽ không gây sai lệch số liệu tồn kho đã xuất hoặc hoàn kho cũ.\\par')
c4_lines.append('  \\item \\textbf{Snapshot điều kiện áp dụng tại \\texttt{CUSTOMER\\_VOUCHERS}:} Khi phát hành voucher, điều kiện giảm giá và phạm vi cơ sở được chụp cố định vào bản ghi voucher. Việc Admin thay đổi chính sách trong danh mục \\texttt{REWARD\\_CATALOG} sẽ không làm ảnh hưởng đến các voucher đã trao tay khách hàng.\\par')
c4_lines.append('\\end{itemize}')
c4_lines.append('')

c4_lines.append('\\section{Bảng tổng hợp đánh giá dạng chuẩn 70 quan hệ}')
c4_lines.append('\\begin{table}[htbp]')
c4_lines.append('\\centering')
c4_lines.append('\\caption{Tổng hợp kết quả đánh giá dạng chuẩn 1NF, 2NF, 3NF của 70 bảng}')
c4_lines.append('\\label{tab:normalization-70}')
c4_lines.append('\\scriptsize')
c4_lines.append('\\begin{tabularx}{\\textwidth}{|>{\\raggedright\\arraybackslash}p{3.2cm}|>{\\centering\\arraybackslash}p{1.0cm}|>{\\centering\\arraybackslash}p{1.0cm}|>{\\centering\\arraybackslash}p{1.6cm}|X|}')
c4_lines.append('\\hline')
c4_lines.append('\\textbf{Tên bảng} & \\textbf{1NF} & \\textbf{2NF} & \\textbf{3NF} & \\textbf{Cơ sở đánh giá và phụ thuộc hàm} \\\\')
c4_lines.append('\\hline')

for domain in domains:
    for tname, rel_name, nf_status, reason in domain['tables']:
        c4_lines.append(f'\\texttt{{{escape_code(tname)}}} & Đạt & Đạt & {nf_status} & {reason} \\\\')
        c4_lines.append('\\hline')

c4_lines.append('\\end{tabularx}')
c4_lines.append('\\end{table}')
c4_lines.append('')

c4_lines.append('\\section{Kết luận chương}')
c4_lines.append('Kết quả phân tích chuẩn hóa cho thấy đại đa số 65/70 bảng trong CyberHub Manager đạt chuẩn 3NF tuyệt đối, đảm bảo không có hiện tượng trùng lặp dữ liệu hay dị thường thêm/sửa/xóa. 5 bảng chứa các trường snapshot (hóa đơn, chi tiết đơn POS, định mức nguyên liệu, voucher) được thiết kế phi chuẩn hóa có kiểm soát nhằm bảo toàn dữ liệu lịch sử kiểm toán tài chính bất biến, được bảo vệ bằng các giao dịch ACID nghiêm ngặt. Mô hình dữ liệu hoàn chỉnh này hoàn toàn sẵn sàng cho việc triển khai vật lý và khai thác truy vấn hiệu năng cao.\\par')

with open('cơ sở dữ liệu/chapters/chuong04.tex', 'w', encoding='utf-8') as f:
    f.write('\n'.join(c4_lines))

print('Generated chuong04.tex with total lines:', len(c4_lines))

