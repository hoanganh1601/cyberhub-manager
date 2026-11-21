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
            ('stores', 'STORES', 'Cơ sở kinh doanh độc lập trong chuỗi phòng máy.'),
            ('employees', 'EMPLOYEES', 'Tài khoản nhân viên đăng nhập, phân quyền RBAC và gán cơ sở chính.'),
            ('employee_profiles', 'EMPLOYEE_PROFILES', 'Hồ sơ nhân sự nghiệp vụ, độc lập với thông tin xác thực.'),
            ('employee_store_assignments', 'EMPLOYEE_STORE_ASSIGNMENTS', 'Phân công đa cơ sở cho quản lý, quan hệ N:M giữa nhân viên và cửa hàng.'),
            ('management_audit', 'MANAGEMENT_AUDIT', 'Sổ nhật ký kiểm toán hành vi quản trị hệ thống.')
        ]
    },
    {
        'title': 'Phân hệ Khách hàng, Hội viên và An ninh tài khoản',
        'tables': [
            ('customers', 'CUSTOMERS', 'Hồ sơ cá nhân khách hàng, định danh qua mã khách và SĐT.'),
            ('customer_store_links', 'CUSTOMER_STORE_LINKS', 'Phạm vi hoạt động và liên kết xác minh của khách hàng tại các cơ sở.'),
            ('accounts', 'ACCOUNTS', 'Tài khoản đăng nhập máy trạm và ví tiền, quan hệ 1:1 với khách hàng.'),
            ('customer_avatars', 'CUSTOMER_AVATARS', 'Ảnh đại diện người dùng đã chuẩn hóa WebP, quan hệ 1:1 với tài khoản.'),
            ('customer_notification_reads', 'CUSTOMER_NOTIFICATION_READS', 'Trạng thái đánh dấu đã đọc thông báo của từng tài khoản.'),
            ('customer_notification_events', 'CUSTOMER_NOTIFICATION_EVENTS', 'Sổ lưu vết thông báo nghiệp vụ gửi đến khách hàng.'),
            ('customer_email_tokens', 'CUSTOMER_EMAIL_TOKENS', 'Mã xác thực email kích hoạt hoặc đặt lại mật khẩu khách hàng.'),
            ('customer_mail_outbox', 'CUSTOMER_MAIL_OUTBOX', 'Hàng đợi thư gửi đi theo mô hình Transactional Outbox.'),
            ('customer_security_audit', 'CUSTOMER_SECURITY_AUDIT', 'Nhật ký kiểm toán an ninh và truy vết thao tác nhạy cảm của khách hàng.')
        ]
    },
    {
        'title': 'Phân hệ Máy trạm, Phòng máy và Quản lý sự cố',
        'tables': [
            ('machines', 'MACHINES', 'Máy trạm vật lý gắn với cửa hàng, quản lý đơn giá giờ chơi và trạng thái.'),
            ('machine_room_types', 'MACHINE_ROOM_TYPES', 'Phân loại phòng máy (Standard, VIP, Couple), quan hệ 1:1 với máy.'),
            ('usage_sessions', 'USAGE_SESSIONS', 'Phiên sử dụng máy trạm của khách hàng, lưu snapshot giá giờ chơi.'),
            ('machine_incidents', 'MACHINE_INCIDENTS', 'Phiếu ghi nhận và theo dõi vòng đời sự cố kỹ thuật của máy trạm.'),
            ('machine_incident_parts', 'MACHINE_INCIDENT_PARTS', 'Danh sách linh kiện và vật tư tiêu hao dùng sửa chữa sự cố.'),
            ('machine_incident_events', 'MACHINE_INCIDENT_EVENTS', 'Lịch sử chuyển đổi trạng thái xử lý sự cố máy trạm.')
        ]
    },
    {
        'title': 'Phân hệ Giao dịch, Hóa đơn và Ca làm việc tiền mặt',
        'tables': [
            ('account_transactions', 'ACCOUNT_TRANSACTIONS', 'Sổ cái bất biến ghi nhận mọi biến động cộng/trừ số dư ví tài khoản.'),
            ('invoices', 'INVOICES', 'Hóa đơn tài chính xuất khi kết thúc phiên chơi, lưu snapshot bối cảnh.'),
            ('cash_shifts', 'CASH_SHIFTS', 'Ca làm việc và sổ kiểm đếm đối soát két tiền mặt của nhân viên.'),
            ('cash_shift_entries', 'CASH_SHIFT_ENTRIES', 'Bút toán chi tiết thu/chi/nạp/rút tiền mặt trong ca làm việc.')
        ]
    },
    {
        'title': 'Phân hệ Thực đơn và Bán hàng POS',
        'tables': [
            ('menu_categories', 'MENU_CATEGORIES', 'Nhóm món ăn/đồ uống theo từng cơ sở.'),
            ('menu_items', 'MENU_ITEMS', 'Món ăn, đồ uống và dịch vụ bán lẻ của cửa hàng.'),
            ('menu_item_images', 'MENU_ITEM_IMAGES', 'Ảnh món ăn đã xử lý WebP chuẩn hóa, quan hệ 1:1 với món.'),
            ('menu_item_changes', 'MENU_ITEM_CHANGES', 'Sổ theo dõi lịch sử điều chỉnh giá và thông tin món ăn.'),
            ('menu_orders', 'MENU_ORDERS', 'Đơn đặt món POS tại quầy hoặc từ máy trạm của khách hàng.'),
            ('menu_order_items', 'MENU_ORDER_ITEMS', 'Chi tiết các dòng món trong đơn POS, lưu snapshot tên và đơn giá lúc đặt.'),
            ('menu_order_pricing', 'MENU_ORDER_PRICING', 'Snapshot kết quả tính giá, chiết khấu và tổng thanh toán của đơn POS.'),
            ('menu_promotions', 'MENU_PROMOTIONS', 'Chính sách khuyến mãi POS theo cơ sở và thời gian.'),
            ('pos_order_reversals', 'POS_ORDER_REVERSALS', 'Yêu cầu hoàn trả/hủy đơn POS theo quy trình Maker-Checker.'),
            ('menu_order_recipe_snapshots', 'MENU_ORDER_RECIPE_SNAPSHOTS', 'Snapshot công thức nguyên liệu tại thời điểm đặt đơn POS.')
        ]
    },
    {
        'title': 'Phân hệ Quản lý kho nguyên liệu và Định lượng',
        'tables': [
            ('inventory_ingredients', 'INVENTORY_INGREDIENTS', 'Nguyên liệu tồn kho theo cơ sở, quản lý tồn thực tế và lượng giữ chỗ.'),
            ('menu_item_recipes', 'MENU_ITEM_RECIPES', 'Bảng định mức công thức chế biến giữa món và nguyên liệu (N:M).'),
            ('inventory_movements', 'INVENTORY_MOVEMENTS', 'Sổ cái kho bất biến ghi nhận mọi biến động nhập, xuất, giữ chỗ, hao hụt.'),
            ('inventory_counts', 'INVENTORY_COUNTS', 'Phiếu kiểm kê định kỳ và đề xuất điều chỉnh số lượng tồn kho.')
        ]
    },
    {
        'title': 'Phân hệ Khuyến mãi nạp tiền, Voucher và Tích điểm',
        'tables': [
            ('promotions', 'PROMOTIONS', 'Chính sách khuyến mãi cộng thưởng theo mốc nạp tiền.'),
            ('loyalty_settings', 'LOYALTY_SETTINGS', 'Cấu hình tỷ lệ tích điểm và quy đổi quyền lợi hội viên.'),
            ('reward_catalog', 'REWARD_CATALOG', 'Danh mục các phần thưởng đổi từ điểm hoặc cấp phát.'),
            ('customer_vouchers', 'CUSTOMER_VOUCHERS', 'Voucher điện tử của khách hàng, lưu snapshot điều kiện lúc phát.'),
            ('voucher_events', 'VOUCHER_EVENTS', 'Nhật ký vòng đời voucher (phát hành, sử dụng, hủy bỏ).'),
            ('loyalty_point_grants', 'LOYALTY_POINT_GRANTS', 'Bản ghi cộng điểm thưởng hội viên từ voucher hoặc sự kiện.')
        ]
    },
    {
        'title': 'Phân hệ Trò chơi giải trí và Vòng quay may mắn',
        'tables': [
            ('games', 'GAMES', 'Cấu hình trò chơi giải trí (vòng quay may mắn, mini-game).'),
            ('game_prizes', 'GAME_PRIZES', 'Danh sách các ô phần thưởng và xác suất trúng thưởng trên vòng quay.'),
            ('game_wallets', 'GAME_WALLETS', 'Ví xu trò chơi riêng biệt của tài khoản, quan hệ 1:1 với tài khoản.'),
            ('game_sessions', 'GAME_SESSIONS', 'Lịch sử từng lượt quay thưởng do máy chủ bốc thăm và xác nhận.'),
            ('game_coin_ledger', 'GAME_COIN_LEDGER', 'Sổ cái biến động số dư xu trò chơi, độc lập với ví tiền mặt.')
        ]
    },
    {
        'title': 'Phân hệ Quảng cáo nhận thưởng',
        'tables': [
            ('ad_settings', 'AD_SETTINGS', 'Cấu hình chính sách xem quảng cáo nhận xu/thời gian chơi.'),
            ('ad_creatives', 'AD_CREATIVES', 'Nội dung và tư liệu quảng cáo nội bộ của hệ thống.'),
            ('ad_reward_events', 'AD_REWARD_EVENTS', 'Sự kiện ghi nhận lượt xem quảng cáo hợp lệ kèm token một lần.')
        ]
    },
    {
        'title': 'Phân hệ Mua sắm, Nhập kho và Công nợ nhà cung cấp',
        'tables': [
            ('suppliers', 'SUPPLIERS', 'Danh bạ nhà cung cấp hàng hóa, nguyên vật liệu và điều khoản thanh toán.'),
            ('purchase_requests', 'PURCHASE_REQUESTS', 'Đề nghị mua sắm nguyên vật liệu do cơ sở khởi tạo.'),
            ('purchase_request_lines', 'PURCHASE_REQUEST_LINES', 'Chi tiết các mặt hàng và số lượng trong đề nghị mua sắm.'),
            ('purchase_orders', 'PURCHASE_ORDERS', 'Đơn đặt hàng chính thức gửi đến nhà cung cấp.'),
            ('purchase_order_lines', 'PURCHASE_ORDER_LINES', 'Chi tiết số lượng và đơn giá từng mặt hàng trong đơn đặt mua.'),
            ('goods_receipts', 'GOODS_RECEIPTS', 'Phiếu nhận hàng thực tế tại kho cơ sở, tạo tự động nhập kho.'),
            ('goods_receipt_lines', 'GOODS_RECEIPT_LINES', 'Chi tiết số lượng thực nhận, hàng đạt, hàng lỗi hoặc thiếu hụt.'),
            ('supplier_payables', 'SUPPLIER_PAYABLES', 'Khoản công nợ phải trả phát sinh từ phiếu nhận hàng.'),
            ('supplier_payable_approvals', 'SUPPLIER_PAYABLE_APPROVALS', 'Bản ghi phê duyệt thanh toán công nợ theo chính sách tách quyền.')
        ]
    },
    {
        'title': 'Phân hệ Đối tác thương mại và Phân phối dịch vụ',
        'tables': [
            ('commercial_partners', 'COMMERCIAL_PARTNERS', 'Thông tin các đối tác cung cấp game bên ngoài hoặc mạng quảng cáo.'),
            ('commercial_contracts', 'COMMERCIAL_CONTRACTS', 'Hợp đồng thương mại quy định mô hình phân chia doanh thu.'),
            ('commercial_campaigns', 'COMMERCIAL_CAMPAIGNS', 'Chiến dịch thương mại trực thuộc hợp đồng đã duyệt.'),
            ('commercial_placements', 'COMMERCIAL_PLACEMENTS', 'Vị trí phân phối nội dung game/quảng cáo tại các cơ sở.'),
            ('commercial_play_sessions', 'COMMERCIAL_PLAY_SESSIONS', 'Phiên chơi dịch vụ đối tác với mã token một lần.'),
            ('commercial_events', 'COMMERCIAL_EVENTS', 'Sổ sự kiện tương tác thương mại (impression, click, complete).'),
            ('commercial_reward_grants', 'COMMERCIAL_REWARD_GRANTS', 'Hàng đợi trả thưởng thương mại đảm bảo xử lý bất đồng bộ an toàn.'),
            ('commercial_settlements', 'COMMERCIAL_SETTLEMENTS', 'Kỳ đối soát và quyết toán doanh thu định kỳ với đối tác.'),
            ('commercial_settlement_lines', 'COMMERCIAL_SETTLEMENT_LINES', 'Chi tiết doanh thu và sản lượng từng vị trí trong kỳ đối soát.')
        ]
    }
]

c3_lines = []
c3_lines.append('\\chapter{Chuyển lược đồ E--R sang các lược đồ quan hệ}')
c3_lines.append('')
c3_lines.append('\\section{Mục tiêu chuyển đổi}')
c3_lines.append('Sau khi đã chuẩn hóa và xác định đầy đủ các thực thể, thuộc tính và liên kết ở Chương 2, bước tiếp theo là chuyển đổi toàn diện mô hình E--R thành tập hợp các lược đồ quan hệ chuẩn tắc có thể cài đặt trực tiếp trong hệ quản trị cơ sở dữ liệu quan hệ MySQL 8.4.\\par')
c3_lines.append('')
c3_lines.append('Kết quả chuyển đổi phản ánh đầy đủ cấu trúc của toàn bộ 70 bảng cơ sở dữ liệu trong CyberHub Manager, làm rõ khóa chính (PK), khóa ngoại (FK), khóa duy nhất (UQ), tính toàn vẹn tham chiếu và chính sách xử lý khi cập nhật/xóa bản ghi.\\par')
c3_lines.append('')
c3_lines.append('\\section{Quy tắc ánh xạ từ E--R sang quan hệ}')
c3_lines.append('\\subsection{Thực thể mạnh}')
c3_lines.append('Mỗi thực thể mạnh độc lập được chuyển thành một quan hệ tương ứng. Định danh nội bộ của thực thể được chuẩn hóa thành cột \\texttt{id} (kiểu \\texttt{BIGINT UNSIGNED AUTO\\_INCREMENT}) đóng vai trò khóa chính. Các thuộc tính đơn trở thành các cột của bảng. Các thuộc tính phức hợp được phân rã thành các cột nguyên tử, và các thuộc tính đa trị được tách thành bảng quan hệ riêng.\\par')
c3_lines.append('')
c3_lines.append('\\subsection{Quan hệ một--nhiều (1:N)}')
c3_lines.append('Với quan hệ 1:N, khóa chính của thực thể phía 1 được đưa sang quan hệ phía N làm khóa ngoại. Ví dụ, quan hệ giữa \\texttt{STORES} và \\texttt{MACHINES}: một cửa hàng sở hữu nhiều máy trạm, do đó cột \\texttt{store\\_id} được đặt trong \\texttt{MACHINES} và tham chiếu đến \\texttt{STORES(id)}. Cột khóa ngoại được quy định \\texttt{NOT NULL} nếu quan hệ có tính tham gia bắt buộc.\\par')
c3_lines.append('')
c3_lines.append('\\subsection{Quan hệ một--một (1:1)}')
c3_lines.append('Với quan hệ 1:1, khóa chính của một phía được đưa sang bảng còn lại làm khóa ngoại kết hợp ràng buộc \\texttt{UNIQUE} để ngăn một giá trị xuất hiện ở nhiều dòng. Trong kiến trúc CyberHub Manager, quan hệ 1:1 xuất hiện ở các cặp bảng như \\texttt{CUSTOMERS} -- \\texttt{ACCOUNTS}, \\texttt{ACCOUNTS} -- \\texttt{CUSTOMER\\_AVATARS}, \\texttt{ACCOUNTS} -- \\texttt{GAME\\_WALLETS}, \\texttt{USAGE\\_SESSIONS} -- \\texttt{INVOICES}, và \\texttt{MENU\\_ITEMS} -- \\texttt{MENU\\_ITEM\\_IMAGES}. Cách thiết kế này tách biệt rõ ràng dữ liệu định danh hồ sơ với dữ liệu bảo mật, media hoặc tài chính.\\par')
c3_lines.append('')
c3_lines.append('\\subsection{Quan hệ nhiều--nhiều (N:M)}')
c3_lines.append('Quan hệ N:M được chuyển hóa thành bảng liên kết trung gian chứa các khóa ngoại tham chiếu đến hai thực thể gốc, kết hợp khóa chính ghép. Điển hình trong hệ thống là bảng phân công quản lý đa cơ sở \\texttt{EMPLOYEE\\_STORE\\_ASSIGNMENTS(employee\\_id, store\\_id)}, bảng công thức định lượng món ăn \\texttt{MENU\\_ITEM\\_RECIPES(item\\_id, ingredient\\_id)}, và bảng chi tiết đặt hàng \\texttt{PURCHASE\\_ORDER\\_LINES(order\\_id, ingredient\\_id)}.\\par')
c3_lines.append('')
c3_lines.append('\\section{Bảng tổng hợp ánh xạ 70 quan hệ theo phân hệ}')
c3_lines.append('Bảng dưới đây tổng hợp toàn bộ 70 bảng quan hệ được ánh xạ từ mô hình E--R sang cơ sở dữ liệu quan hệ vật lý theo từng phân hệ nghiệp vụ:\\par')
c3_lines.append('')
c3_lines.append('\\begin{table}[htbp]')
c3_lines.append('\\centering')
c3_lines.append('\\caption{Bảng ánh xạ tổng thể 70 quan hệ trong CyberHub Manager}')
c3_lines.append('\\label{tab:relational-mapping-70}')
c3_lines.append('\\scriptsize')
c3_lines.append('\\begin{tabularx}{\\textwidth}{|>{\\raggedright\\arraybackslash}p{2.8cm}|>{\\raggedright\\arraybackslash}p{3.5cm}|X|}')
c3_lines.append('\\hline')
c3_lines.append('\\textbf{Phân hệ} & \\textbf{Tên bảng quan hệ} & \\textbf{Đặc điểm ánh xạ và khóa chính/khóa ngoại} \\\\')
c3_lines.append('\\hline')

for domain in domains:
    dtitle_short = domain['title'].replace('Phân hệ ', '')
    num_tbls = len(domain['tables'])
    for idx, (tname, rel_name, rdesc) in enumerate(domain['tables']):
        sec_prefix = f'\\multirow{{{num_tbls}}}{{=}}{{{dtitle_short}}}' if idx == 0 else ''
        c3_lines.append(f'{sec_prefix} & \\texttt{{{escape_code(tname)}}} & {rdesc} \\\\')
        c3_lines.append('\\hline')

c3_lines.append('\\end{tabularx}')
c3_lines.append('\\end{table}')
c3_lines.append('')

c3_lines.append('\\section{Lược đồ quan hệ logic chi tiết của 70 bảng}')
c3_lines.append('Dưới đây là biểu diễn hình thức lược đồ logic của toàn bộ 70 quan hệ. Các thuộc tính khóa chính được \\underline{gạch chân}, khóa ngoại được ký hiệu bằng chỉ số tham chiếu tương ứng:\\par')
c3_lines.append('')

for d_idx, domain in enumerate(domains, 1):
    dtitle = domain['title']
    c3_lines.append(f'\\subsection{{{dtitle}}}')
    
    for tname, rel_name, rdesc in domain['tables']:
        p = parsed_tables.get(tname, {})
        cols = p.get('cols', [])
        
        pk_cols = [c[0] for c in cols if 'PK' in c[4]]
        other_cols = [c[0] for c in cols if 'PK' not in c[4]]
        
        # Build schema string
        schema_items = []
        for cname in pk_cols:
            schema_items.append(f'\\underline{{{escape_code(cname)}}}')
        for cname in other_cols:
            schema_items.append(f'{escape_code(cname)}')
        
        schema_str = f'\\textbf{{{rel_name}}}({", ".join(schema_items)})'
        
        c3_lines.append(f'\\subsubsection{{{rel_name} -- \\texttt{{{escape_code(tname)}}}}}')
        c3_lines.append('\\[')
        c3_lines.append(f'{schema_str}')
        c3_lines.append('\\]')
        
        # List PK, FK, UQ
        fks = []
        uqs = []
        for c in cols:
            if 'FK' in c[4]:
                fk_clean = c[4].replace('FK', '').replace('→', '').strip()
                fks.append(f'\\texttt{{{escape_code(c[0])}}} $\\rightarrow$ \\texttt{{{escape_code(fk_clean)}}}')
            if ('UK' in c[4] or 'UQ' in c[4]) and 'PK' not in c[4]:
                uqs.append(f'\\texttt{{{escape_code(c[0])}}}')
        
        c3_lines.append('\\begin{itemize}')
        pk_formatted = ", ".join(['\\texttt{' + escape_code(x) + '}' for x in pk_cols])
        c3_lines.append(f'  \\item \\textbf{{Khóa chính (PK):}} {pk_formatted}.')
        if fks:
            c3_lines.append(f'  \\item \\textbf{{Khóa ngoại (FK):}} {"; ".join(fks)}.')
        if uqs:
            c3_lines.append(f'  \\item \\textbf{{Khóa duy nhất (UQ):}} {", ".join(uqs)}.')
        c3_lines.append(f'  \\item \\textbf{{Ý nghĩa nghiệp vụ:}} {escape_latex(p.get("meaning", ""))}')
        c3_lines.append('\\end{itemize}')
        c3_lines.append('')

c3_lines.append('\\section{Từ lược đồ logic đến lược đồ vật lý}')
c3_lines.append('Trong MySQL 8.4, toàn bộ 70 bảng trên được cài đặt với lưu trữ InnoDB. Khóa định danh tự tăng sử dụng \\texttt{BIGINT UNSIGNED AUTO\\_INCREMENT}; tiền tệ dùng \\texttt{BIGINT}; thời gian dùng \\texttt{DATETIME} chuẩn UTC; chuỗi ký tự dùng \\texttt{VARCHAR} hoặc \\texttt{CHAR} với bộ mã \\texttt{utf8mb4}. Toàn bộ ràng buộc toàn vẹn tham chiếu FOREIGN KEY, UNIQUE và CHECK đều được khai báo tường minh trong các tập tin migration DDL.\\par')
c3_lines.append('')
c3_lines.append('\\begin{figure}[htbp]')
c3_lines.append('  \\centering')
c3_lines.append('  \\includegraphics[width=0.98\\textwidth,height=0.65\\textheight,keepaspectratio]{figures/erd_physical.png}')
c3_lines.append('  \\caption{Sơ đồ quan hệ vật lý (Physical ERD) của mô hình lõi trong MySQL}')
c3_lines.append('  \\label{fig:erd-physical}')
c3_lines.append('\\end{figure}')
c3_lines.append('')
c3_lines.append('Đặc biệt, để ngăn chặn tình trạng một máy trạm hoặc một khách hàng có đồng thời hai phiên ACTIVE, hệ thống áp dụng kỹ thuật cột sinh ảo lưu trữ (Stored Generated Columns) \\texttt{active\\_machine\\_id} và \\texttt{active\\_customer\\_id} kết hợp ràng buộc \\texttt{UNIQUE INDEX}. Kỹ thuật này tận dụng khả năng cho phép nhiều giá trị NULL trong chỉ mục UNIQUE của MySQL để kiểm soát đồng thời mà không cần trigger phức tạp.\\par')
c3_lines.append('')
c3_lines.append('\\section{Kiểm tra các quan hệ sau ánh xạ}')
c3_lines.append('\\subsection{Bảo toàn lực lượng kết hợp}')
c3_lines.append('Tất cả các mối quan hệ 1:N, 1:1 và N:M đều được bảo toàn trọn vẹn thông qua hệ thống khóa ngoại và khóa duy nhất tương ứng. Các cột khóa ngoại bắt buộc (NOT NULL) đảm bảo bản ghi con không bao giờ bị mồ côi, trong khi các khóa ngoại tùy chọn (NULLABLE) phản ánh chính xác trạng thái nghiệp vụ chưa phát sinh (ví dụ nhân viên đóng phiên chưa có khi phiên đang chạy, hoặc mã khuyến mãi để trống khi không áp dụng ưu đãi).\\par')
c3_lines.append('')
c3_lines.append('\\subsection{Chính sách toàn vẹn tham chiếu}')
c3_lines.append('Hệ thống áp dụng chính sách toàn vẹn tham chiếu khắt khe: toàn bộ các bảng lịch sử nghiệp vụ, tài chính, hóa đơn và sổ cái đều sử dụng \\texttt{ON UPDATE RESTRICT ON DELETE RESTRICT}. Chỉ các bảng phân loại phụ trợ (như \\texttt{machine\\_room\\_types}) hoặc bảng dữ liệu media gắn chặt với thực thể cha (như \\texttt{customer\\_avatars}, \\texttt{menu\\_item\\_images}) mới được phép dùng \\texttt{CASCADE} khi thực thể chính được phép xóa. Điều này đảm bảo tính toàn vẹn và khả năng kiểm toán lịch sử không thể bị xâm phạm.\\par')
c3_lines.append('')
c3_lines.append('\\section{Kết luận chương}')
c3_lines.append('Quá trình ánh xạ đã chuyển đổi hoàn chỉnh 70 thực thể E--R thành 70 bảng quan hệ chuẩn tắc trong MySQL 8.4. Cấu trúc logic và vật lý thu được bảo toàn tuyệt đối mọi ràng buộc nghiệp vụ, tạo nền tảng vững chắc để phân tích chuẩn hóa dạng chuẩn 3NF tại Chương 4.\\par')

with open('cơ sở dữ liệu/chapters/chuong03.tex', 'w', encoding='utf-8') as f:
    f.write('\n'.join(c3_lines))

print('Generated chuong03.tex with total lines:', len(c3_lines))
