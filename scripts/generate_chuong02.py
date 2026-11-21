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
            ('stores', 'Cửa hàng (STORE)'),
            ('employees', 'Nhân viên (EMPLOYEE)'),
            ('employee_profiles', 'Hồ sơ nhân sự (EMPLOYEE\\_PROFILE)'),
            ('employee_store_assignments', 'Phân công nhân viên đa cơ sở (EMPLOYEE\\_STORE\\_ASSIGNMENT)'),
            ('management_audit', 'Nhật ký kiểm toán quản trị (MANAGEMENT\\_AUDIT)')
        ]
    },
    {
        'title': 'Phân hệ Khách hàng, Hội viên và An ninh tài khoản',
        'tables': [
            ('customers', 'Khách hàng (CUSTOMER)'),
            ('customer_store_links', 'Liên kết khách hàng -- cơ sở (CUSTOMER\\_STORE\\_LINK)'),
            ('accounts', 'Tài khoản khách hàng (ACCOUNT)'),
            ('customer_avatars', 'Ảnh đại diện khách hàng (CUSTOMER\\_AVATAR)'),
            ('customer_notification_reads', 'Trạng thái đọc thông báo (CUSTOMER\\_NOTIFICATION\\_READ)'),
            ('customer_notification_events', 'Nhật ký sự kiện thông báo (CUSTOMER\\_NOTIFICATION\\_EVENT)'),
            ('customer_email_tokens', 'Mã xác thực email (CUSTOMER\\_EMAIL\\_TOKEN)'),
            ('customer_mail_outbox', 'Hàng đợi gửi email (CUSTOMER\\_MAIL\\_OUTBOX)'),
            ('customer_security_audit', 'Nhật ký kiểm toán an ninh (CUSTOMER\\_SECURITY\\_AUDIT)')
        ]
    },
    {
        'title': 'Phân hệ Máy trạm, Phòng máy và Quản lý sự cố',
        'tables': [
            ('machines', 'Máy trạm (MACHINE)'),
            ('machine_room_types', 'Phân loại phòng máy trạm (MACHINE\\_ROOM\\_TYPE)'),
            ('usage_sessions', 'Phiên sử dụng máy (USAGE\\_SESSION)'),
            ('machine_incidents', 'Sự cố máy trạm (MACHINE\\_INCIDENT)'),
            ('machine_incident_parts', 'Linh kiện xử lý sự cố (MACHINE\\_INCIDENT\\_PART)'),
            ('machine_incident_events', 'Lịch sử xử lý sự cố máy (MACHINE\\_INCIDENT\\_EVENT)')
        ]
    },
    {
        'title': 'Phân hệ Giao dịch, Hóa đơn và Ca làm việc tiền mặt',
        'tables': [
            ('account_transactions', 'Giao dịch tài khoản ví (ACCOUNT\\_TRANSACTION)'),
            ('invoices', 'Hóa đơn thanh toán (INVOICE)'),
            ('cash_shifts', 'Ca làm việc tiền mặt (CASH\\_SHIFT)'),
            ('cash_shift_entries', 'Bút toán sổ quỹ ca làm việc (CASH\\_SHIFT\\_ENTRY)')
        ]
    },
    {
        'title': 'Phân hệ Thực đơn và Bán hàng POS',
        'tables': [
            ('menu_categories', 'Danh mục thực đơn (MENU\\_CATEGORY)'),
            ('menu_items', 'Món thực đơn (MENU\\_ITEM)'),
            ('menu_item_images', 'Hình ảnh món thực đơn (MENU\\_ITEM\\_IMAGE)'),
            ('menu_item_changes', 'Lịch sử thay đổi món (MENU\\_ITEM\\_CHANGE)'),
            ('menu_orders', 'Đơn đặt món POS (MENU\\_ORDER)'),
            ('menu_order_items', 'Chi tiết món trong đơn POS (MENU\\_ORDER\\_ITEM)'),
            ('menu_order_pricing', 'Snapshot bảng giá đơn POS (MENU\\_ORDER\\_PRICING)'),
            ('menu_promotions', 'Chính sách khuyến mãi POS (MENU\\_PROMOTION)'),
            ('pos_order_reversals', 'Yêu cầu hoàn/hủy đơn POS (POS\\_ORDER\\_REVERSAL)'),
            ('menu_order_recipe_snapshots', 'Snapshot công thức định lượng đơn (MENU\\_ORDER\\_RECIPE\\_SNAPSHOT)')
        ]
    },
    {
        'title': 'Phân hệ Quản lý kho nguyên liệu và Định lượng',
        'tables': [
            ('inventory_ingredients', 'Nguyên liệu tồn kho (INVENTORY\\_INGREDIENT)'),
            ('menu_item_recipes', 'Công thức định lượng món (MENU\\_ITEM\\_RECIPE)'),
            ('inventory_movements', 'Biến động sổ cái kho (INVENTORY\\_MOVEMENT)'),
            ('inventory_counts', 'Phiếu kiểm kê kho (INVENTORY\\_COUNT)')
        ]
    },
    {
        'title': 'Phân hệ Khuyến mãi nạp tiền, Voucher và Tích điểm',
        'tables': [
            ('promotions', 'Chính sách khuyến mãi nạp tiền (PROMOTION)'),
            ('loyalty_settings', 'Cấu hình tích điểm thành viên (LOYALTY\\_SETTING)'),
            ('reward_catalog', 'Danh mục phần thưởng (REWARD\\_CATALOG)'),
            ('customer_vouchers', 'Voucher khách hàng (CUSTOMER\\_VOUCHER)'),
            ('voucher_events', 'Nhật ký sự kiện voucher (VOUCHER\\_EVENT)'),
            ('loyalty_point_grants', 'Cấp điểm thưởng hội viên (LOYALTY\\_POINT\\_GRANT)')
        ]
    },
    {
        'title': 'Phân hệ Trò chơi giải trí và Vòng quay may mắn',
        'tables': [
            ('games', 'Cấu hình trò chơi (GAME)'),
            ('game_prizes', 'Cơ cấu giải thưởng trò chơi (GAME\\_PRIZE)'),
            ('game_wallets', 'Ví xu trò chơi (GAME\\_WALLET)'),
            ('game_sessions', 'Phiên quay thưởng trò chơi (GAME\\_SESSION)'),
            ('game_coin_ledger', 'Sổ cái biến động xu trò chơi (GAME\\_COIN\\_LEDGER)')
        ]
    },
    {
        'title': 'Phân hệ Quảng cáo nhận thưởng',
        'tables': [
            ('ad_settings', 'Cấu hình quảng cáo nhận thưởng (AD\\_SETTING)'),
            ('ad_creatives', 'Nội dung quảng cáo sáng tạo (AD\\_CREATIVE)'),
            ('ad_reward_events', 'Sự kiện xem quảng cáo nhận thưởng (AD\\_REWARD\\_EVENT)')
        ]
    },
    {
        'title': 'Phân hệ Mua sắm, Nhập kho và Công nợ nhà cung cấp',
        'tables': [
            ('suppliers', 'Nhà cung cấp (SUPPLIER)'),
            ('purchase_requests', 'Đề nghị mua sắm (PURCHASE\\_REQUEST)'),
            ('purchase_request_lines', 'Chi tiết đề nghị mua sắm (PURCHASE\\_REQUEST\\_LINE)'),
            ('purchase_orders', 'Đơn đặt mua hàng (PURCHASE\\_ORDER)'),
            ('purchase_order_lines', 'Chi tiết đơn đặt mua hàng (PURCHASE\\_ORDER\\_LINE)'),
            ('goods_receipts', 'Phiếu nhập kho hàng hóa (GOODS\\_RECEIPT)'),
            ('goods_receipt_lines', 'Chi tiết phiếu nhập kho (GOODS\\_RECEIPT\\_LINE)'),
            ('supplier_payables', 'Công nợ phải trả nhà cung cấp (SUPPLIER\\_PAYABLE)'),
            ('supplier_payable_approvals', 'Phê duyệt công nợ nhà cung cấp (SUPPLIER\\_PAYABLE\\_APPROVAL)')
        ]
    },
    {
        'title': 'Phân hệ Đối tác thương mại và Phân phối dịch vụ',
        'tables': [
            ('commercial_partners', 'Đối tác thương mại (COMMERCIAL\\_PARTNER)'),
            ('commercial_contracts', 'Hợp đồng thương mại (COMMERCIAL\\_CONTRACT)'),
            ('commercial_campaigns', 'Chiến dịch thương mại (COMMERCIAL\\_CAMPAIGN)'),
            ('commercial_placements', 'Vị trí phân phối thương mại (COMMERCIAL\\_PLACEMENT)'),
            ('commercial_play_sessions', 'Phiên chơi đối tác thương mại (COMMERCIAL\\_PLAY\\_SESSION)'),
            ('commercial_events', 'Sự kiện tương tác thương mại (COMMERCIAL\\_EVENT)'),
            ('commercial_reward_grants', 'Hàng đợi cấp thưởng thương mại (COMMERCIAL\\_REWARD\\_GRANT)'),
            ('commercial_settlements', 'Kỳ đối soát quyết toán (COMMERCIAL\\_SETTLEMENT)'),
            ('commercial_settlement_lines', 'Chi tiết kỳ đối soát quyết toán (COMMERCIAL\\_SETTLEMENT\\_LINE)')
        ]
    }
]

# Generate chuong02.tex
c2_lines = []
c2_lines.append('\\chapter{Lược đồ E--R và mô tả dữ liệu}')
c2_lines.append('')
c2_lines.append('\\section{Lược đồ E--R}')
c2_lines.append('')
c2_lines.append('\\subsection{Mục tiêu và phạm vi mô hình}')
c2_lines.append('Mô hình thực thể--kết hợp (Entity--Relationship, viết tắt E--R) mô tả toàn bộ các đối tượng nghiệp vụ cần quản lý trong hệ thống CyberHub Manager, các thuộc tính nhận diện chúng và các mối liên hệ ràng buộc đa chiều giữa các đối tượng. Đây là bước chuyển từ kịch bản thế giới thực sang thiết kế dữ liệu logic và vật lý.\\par')
c2_lines.append('')
c2_lines.append('Trong phiên bản vận hành hoàn chỉnh với 27 đợt cập nhật schema (từ migration \\texttt{001\\_initial\\_schema.sql} đến \\texttt{027\\_customer\\_email\\_activation.sql}), hệ thống quản lý tổng cộng 70 bảng cơ sở dữ liệu. Để đảm bảo tính sư phạm và khả năng tiếp cận có hệ thống, mô hình E--R được tổ chức thành hai cấp độ: sơ đồ E--R quan niệm cho 8 thực thể lõi (P0) chi phối vòng đời dịch vụ giờ chơi; tiếp theo đó là 11 phân hệ chức năng hoàn chỉnh bao quát toàn bộ 70 bảng cơ sở dữ liệu nghiệp vụ.\\par')
c2_lines.append('')
c2_lines.append('\\subsection{Sơ đồ E--R quan niệm cốt lõi}')
c2_lines.append('\\begin{figure}[htbp]')
c2_lines.append('  \\centering')
c2_lines.append('  \\includegraphics[width=0.98\\textwidth,height=0.66\\textheight,keepaspectratio]{figures/erd_conceptual.png}')
c2_lines.append('  \\caption{Sơ đồ E--R quan niệm của các nghiệp vụ cốt lõi}')
c2_lines.append('  \\label{fig:erd-core}')
c2_lines.append('\\end{figure}')
c2_lines.append('')
c2_lines.append('Trong ký pháp Crow\\\'s Foot thể hiện trên hình, đầu có một gạch biểu diễn đúng một; vòng tròn biểu diễn số lượng tối thiểu bằng 0; chân quạ biểu diễn nhiều. Vì vậy, ký hiệu vòng tròn kèm chân quạ biểu thị \\textbf{0..N}, còn một gạch biểu thị \\textbf{đúng một}. Các quan hệ có đầu tùy chọn cho phép dữ liệu chưa phát sinh ở phía liên quan.\\par')
c2_lines.append('')
c2_lines.append('\\subsection{Diễn giải các mối quan hệ và lực lượng kết hợp cốt lõi}')
c2_lines.append('\\begin{table}[htbp]')
c2_lines.append('\\centering')
c2_lines.append('\\caption{Các quan hệ chính trong mô hình E--R cốt lõi}')
c2_lines.append('\\label{tab:er-relationships}')
c2_lines.append('\\small')
c2_lines.append('\\begin{tabularx}{\\textwidth}{|>{\\raggedright\\arraybackslash}p{3.15cm}|>{\\centering\\arraybackslash}p{2.2cm}|X|}')
c2_lines.append('\\hline')
c2_lines.append('\\textbf{Quan hệ} & \\textbf{Lực lượng} & \\textbf{Diễn giải nghiệp vụ} \\\\')
c2_lines.append('\\hline')
c2_lines.append('STORE -- EMPLOYEE & 1 : 0..N & Một cửa hàng có thể quản lý nhiều nhân viên; mỗi nhân viên thuộc đúng một cửa hàng. \\\\')
c2_lines.append('\\hline')
c2_lines.append('STORE -- MACHINE & 1 : 0..N & Một cửa hàng có thể quản lý nhiều máy; mỗi máy thuộc đúng một cửa hàng. \\\\')
c2_lines.append('\\hline')
c2_lines.append('STORE -- INVOICE & 1 : 0..N & Một cửa hàng có thể phát sinh nhiều hóa đơn; mỗi hóa đơn được ghi nhận cho một cửa hàng. \\\\')
c2_lines.append('\\hline')
c2_lines.append('CUSTOMER -- ACCOUNT & 1 : 1 (nghiệp vụ) & Mỗi khách hàng được tạo một tài khoản và mỗi tài khoản thuộc một khách hàng. DDL bảo đảm tối đa một tài khoản/khách bằng UNIQUE. \\\\')
c2_lines.append('\\hline')
c2_lines.append('CUSTOMER -- USAGE\\_SESSION & 1 : 0..N & Một khách có thể sử dụng dịch vụ nhiều lần theo thời gian; mỗi phiên thuộc một khách. \\\\')
c2_lines.append('\\hline')
c2_lines.append('MACHINE -- USAGE\\_SESSION & 1 : 0..N & Một máy có nhiều phiên lịch sử; mỗi phiên diễn ra trên một máy. Mỗi máy chỉ có tối đa một phiên ACTIVE đồng thời. \\\\')
c2_lines.append('\\hline')
c2_lines.append('EMPLOYEE -- USAGE\\_SESSION & mở: 1 : 0..N; đóng: 0..1 : 0..N & Mỗi phiên bắt buộc có một nhân viên mở. Nhân viên đóng chỉ được ghi nhận khi phiên kết thúc. \\\\')
c2_lines.append('\\hline')
c2_lines.append('ACCOUNT -- ACCOUNT\\_TRANSACTION & 1 : 0..N & Một tài khoản có thể có nhiều giao dịch; mỗi giao dịch tác động đến đúng một tài khoản. \\\\')
c2_lines.append('\\hline')
c2_lines.append('EMPLOYEE -- ACCOUNT\\_TRANSACTION & 1 : 0..N & Mỗi giao dịch do một nhân viên ghi nhận; một nhân viên có thể ghi nhận nhiều giao dịch. \\\\')
c2_lines.append('\\hline')
c2_lines.append('USAGE\\_SESSION -- ACCOUNT\\_TRANSACTION & 0..1 : 0..N & Giao dịch có thể liên kết với phiên (thanh toán sử dụng); giao dịch nạp tiền độc lập có thể không gắn phiên. \\\\')
c2_lines.append('\\hline')
c2_lines.append('USAGE\\_SESSION -- INVOICE & 1 : 0..1 & Một phiên có thể chưa có hóa đơn khi chưa checkout và tạo tối đa một hóa đơn; mỗi hóa đơn bắt buộc thuộc một phiên. \\\\')
c2_lines.append('\\hline')
c2_lines.append('CUSTOMER -- INVOICE & 1 : 0..N & Khách hàng có thể nhận nhiều hóa đơn theo các phiên khác nhau; mỗi hóa đơn lưu một khách hàng. \\\\')
c2_lines.append('\\hline')
c2_lines.append('EMPLOYEE -- INVOICE & 1 : 0..N & Nhân viên checkout có thể lập nhiều hóa đơn; mỗi hóa đơn lưu nhân viên thực hiện. \\\\')
c2_lines.append('\\hline')
c2_lines.append('\\end{tabularx}')
c2_lines.append('\\end{table}')
c2_lines.append('')
c2_lines.append('\\section{Mô tả chi tiết 70 thực thể theo các phân hệ nghiệp vụ}')
c2_lines.append('Nhằm phản ánh trung thực và toàn diện toàn bộ 70 bảng cơ sở dữ liệu trong schema MySQL 8.4 của CyberHub Manager, phần này trình bày chi tiết từng thực thể theo 11 phân hệ chức năng. Mỗi thực thể đều nêu rõ ý nghĩa nghiệp vụ, danh sách thuộc tính (kèm vai trò PK, FK, UQ), miền giá trị và các quy tắc toàn vẹn (CHECK constraints, foreign key behaviors) được cài đặt thực tế trong các tệp migration.\\par')
c2_lines.append('')

for d_idx, domain in enumerate(domains, 1):
    c2_lines.append(f'\\subsection{{{domain["title"]}}}')
    c2_lines.append(f'Phân hệ này bao gồm {len(domain["tables"])} thực thể đảm nhiệm các luồng dữ liệu nghiệp vụ đặc thù:\\par')
    c2_lines.append('')
    
    for tname, tlabel in domain['tables']:
        p = parsed_tables.get(tname, {})
        c2_lines.append(f'\\subsubsection{{{tlabel} -- \\texttt{{{escape_code(tname)}}}}}')
        c2_lines.append(f'\\textbf{{Ý nghĩa:}} {escape_latex(p.get("meaning", ""))}\\par')
        c2_lines.append('')
        
        cols_formatted = []
        for cname, ctype, cnull, cdef, ckey, cmean in p.get('cols', []):
            role_parts = []
            if 'PK' in ckey:
                role_parts.append('PK')
            if 'UK' in ckey or 'UQ' in ckey:
                role_parts.append('UQ')
            if 'FK' in ckey:
                fk_clean = ckey.replace('FK', '').replace('→', '').strip()
                role_parts.append(f'FK đến \\texttt{{{escape_code(fk_clean)}}}')
            if cnull == 'Có':
                role_parts.append('NULL')
            
            role_str = f' ({", ".join(role_parts)})' if role_parts else ''
            cols_formatted.append(f'\\texttt{{{escape_code(cname)}}}{role_str}')
        
        c2_lines.append(f'\\textbf{{Thuộc tính:}} {", ".join(cols_formatted)}.\\par')
        c2_lines.append('')
        
        rules_text = []
        for r in p.get('rules', []):
            if r.startswith('- '):
                r_content = r[2:].strip()
                rules_text.append(f'\\item {escape_latex(r_content)}')
        
        if rules_text:
            c2_lines.append('\\textbf{{Miền và quy tắc:}}')
            c2_lines.append('\\begin{itemize}')
            c2_lines.extend(rules_text)
            c2_lines.append('\\end{itemize}')
        else:
            c2_lines.append('\\textbf{{Miền và quy tắc:}} Tuân thủ kiểu dữ liệu chuẩn và tính toàn vẹn khóa ngoại.\\par')
        c2_lines.append('')

c2_lines.append('\\section{Khóa, miền dữ liệu và tính toàn vẹn}')
c2_lines.append('\\subsection{Các loại khóa sử dụng}')
c2_lines.append('\\begin{itemize}')
c2_lines.append('  \\item \\textbf{Khóa chính (PK):} 70 bảng đều sử dụng \\texttt{id} (\\texttt{bigint unsigned auto\\_increment}) hoặc khóa chính ghép tự nhiên (ví dụ \\texttt{employee\\_store\\_assignments(employee\\_id, store\\_id)}, \\texttt{menu\\_item\\_recipes(item\\_id, ingredient\\_id)}) để định danh duy nhất từng bản ghi.')
c2_lines.append('  \\item \\textbf{Khóa duy nhất nghiệp vụ (UQ):} Ràng buộc \\texttt{UNIQUE} bảo vệ các mã định danh có tiền tố nghiệp vụ như \\texttt{code}, tên đăng nhập, số điện thoại, email và token.')
c2_lines.append('  \\item \\textbf{Khóa ngoại (FK):} Biểu diễn toàn bộ các mối quan hệ tham chiếu 1:N và 1:1, ngăn ngừa bản ghi con mồ côi.')
c2_lines.append('  \\item \\textbf{Khóa duy nhất trên khóa ngoại:} Thiết lập quan hệ 1:1 nghiêm ngặt giữa hồ sơ nhân sự, tài khoản khách hàng, hóa đơn phiên và snapshot giá POS.')
c2_lines.append('\\end{itemize}')
c2_lines.append('')
c2_lines.append('\\subsection{Miền dữ liệu và quy ước lưu trữ}')
c2_lines.append('Toàn bộ các giá trị tiền tệ VND được lưu trữ bằng \\texttt{BIGINT} có dấu hoặc không dấu; tuyệt đối không dùng số thực để tránh sai số dấu phẩy động. Thời gian lưu trữ bằng \\texttt{DATETIME} theo chuẩn UTC quốc tế; tầng giao diện chịu trách nhiệm chuyển đổi sang múi giờ Việt Nam. Các trường trạng thái được bảo vệ bằng ràng buộc \\texttt{CHECK (status IN (...))} thay vì chuỗi tự do. Bộ mã ký tự \\texttt{utf8mb4} với collation \\texttt{utf8mb4\\_0900\\_ai\\_ci} bảo đảm hiển thị tiếng Việt chính xác trên toàn hệ thống.\\par')
c2_lines.append('')
c2_lines.append('\\section{Kết luận chương}')
c2_lines.append('Chương này đã hoàn thành việc mô tả toàn diện cấu trúc dữ liệu của CyberHub Manager từ sơ đồ E--R quan niệm cốt lõi đến 70 thực thể chi tiết phân bố trong 11 phân hệ nghiệp vụ. Việc xác lập rõ ràng ý nghĩa, thuộc tính và các quy tắc toàn vẹn là tiền đề vững chắc để thực hiện ánh xạ sang các lược đồ quan hệ logic và vật lý tại Chương 3.\\par')

with open('cơ sở dữ liệu/chapters/chuong02.tex', 'w', encoding='utf-8') as f:
    f.write('\n'.join(c2_lines))

print('Generated chuong02.tex with total lines:', len(c2_lines))

