"""Persistence for supplier purchasing and stock receiving."""

from cyberhub_manager.infrastructure.repositories.sql import execute, rows


class ProcurementRepository:
    def list_suppliers(self, conn, store_id):
        return rows(conn,"SELECT * FROM suppliers WHERE store_id=%s ORDER BY is_active DESC,name,id",(store_id,))

    def supplier(self, conn, supplier_id, *, lock=False):
        result=rows(conn,"SELECT * FROM suppliers WHERE id=%s"+(" FOR UPDATE" if lock else ""),(supplier_id,))
        return result[0] if result else None

    def save_supplier(self, conn, *, supplier_id, store_id, code, name, phone, email,
                      address, payment_terms_days, is_active):
        if supplier_id:
            execute(conn,"UPDATE suppliers SET code=%s,name=%s,phone=%s,email=%s,address=%s,"
                    "payment_terms_days=%s,is_active=%s WHERE id=%s AND store_id=%s",
                    (code,name,phone,email,address,payment_terms_days,is_active,supplier_id,store_id))
            return supplier_id
        return execute(conn,"INSERT INTO suppliers(store_id,code,name,phone,email,address,payment_terms_days,is_active) "
                       "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                       (store_id,code,name,phone,email,address,payment_terms_days,is_active))

    def ingredients(self, conn, store_id):
        return rows(conn,"SELECT id,code,name,unit,on_hand,reserved,reorder_point FROM inventory_ingredients "
                    "WHERE store_id=%s AND is_active=TRUE ORDER BY name,id",(store_id,))

    def create_request(self, conn, *, code, store_id, employee_id, reason, lines):
        request_id=execute(conn,"INSERT INTO purchase_requests(code,store_id,requested_by,reason) VALUES(%s,%s,%s,%s)",
                           (code,store_id,employee_id,reason))
        for line in lines:
            execute(conn,"INSERT INTO purchase_request_lines(request_id,ingredient_id,quantity) VALUES(%s,%s,%s)",
                    (request_id,line["ingredient_id"],line["quantity"]))
        return request_id

    def request(self, conn, request_id, *, lock=False):
        result=rows(conn,"SELECT r.*,e.full_name AS requester_name,d.full_name AS decider_name "
                    "FROM purchase_requests r JOIN employees e ON e.id=r.requested_by "
                    "LEFT JOIN employees d ON d.id=r.decided_by WHERE r.id=%s"+
                    (" FOR UPDATE" if lock else ""),(request_id,))
        return result[0] if result else None

    def request_lines(self, conn, request_id):
        return rows(conn,"SELECT l.*,i.code AS ingredient_code,i.name AS ingredient_name,i.unit "
                    "FROM purchase_request_lines l JOIN inventory_ingredients i ON i.id=l.ingredient_id "
                    "WHERE l.request_id=%s ORDER BY i.name,i.id",(request_id,))

    def list_requests(self, conn, store_id):
        return rows(conn,"SELECT r.*,e.full_name AS requester_name,d.full_name AS decider_name "
                    "FROM purchase_requests r JOIN employees e ON e.id=r.requested_by "
                    "LEFT JOIN employees d ON d.id=r.decided_by WHERE r.store_id=%s "
                    "ORDER BY r.created_at DESC,r.id DESC LIMIT 200",(store_id,))

    def decide_request(self, conn, request_id, employee_id, approve):
        return execute(conn,"UPDATE purchase_requests SET status=%s,decided_by=%s,decided_at=UTC_TIMESTAMP() "
                       "WHERE id=%s AND status='PENDING'",("APPROVED" if approve else "REJECTED",employee_id,request_id))

    def create_order(self, conn, *, code, request, supplier_id, employee_id, expected_at, lines):
        total=sum(line["quantity"]*line["unit_cost"] for line in lines)
        order_id=execute(conn,"INSERT INTO purchase_orders(code,store_id,request_id,supplier_id,created_by,expected_at,total_amount) "
                         "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                         (code,request["store_id"],request["id"],supplier_id,employee_id,expected_at,total))
        for line in lines:
            execute(conn,"INSERT INTO purchase_order_lines(order_id,ingredient_id,quantity,unit_cost) VALUES(%s,%s,%s,%s)",
                    (order_id,line["ingredient_id"],line["quantity"],line["unit_cost"]))
        execute(conn,"UPDATE purchase_requests SET status='ORDERED' WHERE id=%s AND status='APPROVED'",(request["id"],))
        return order_id

    def order(self, conn, order_id, *, lock=False):
        result=rows(conn,"SELECT o.*,s.name AS supplier_name,s.payment_terms_days FROM purchase_orders o "
                    "JOIN suppliers s ON s.id=o.supplier_id WHERE o.id=%s"+
                    (" FOR UPDATE" if lock else ""),(order_id,))
        return result[0] if result else None

    def order_lines(self, conn, order_id, *, lock=False):
        return rows(conn,"SELECT l.*,i.name AS ingredient_name,i.unit,i.store_id FROM purchase_order_lines l "
                    "JOIN inventory_ingredients i ON i.id=l.ingredient_id WHERE l.order_id=%s ORDER BY l.ingredient_id"+
                    (" FOR UPDATE" if lock else ""),(order_id,))

    def list_orders(self, conn, store_id):
        return rows(conn,"SELECT o.*,s.name AS supplier_name FROM purchase_orders o JOIN suppliers s ON s.id=o.supplier_id "
                    "WHERE o.store_id=%s ORDER BY o.ordered_at DESC,o.id DESC LIMIT 200",(store_id,))

    def receipt_by_request(self, conn, request_id, *, lock=False):
        result=rows(conn,"SELECT * FROM goods_receipts WHERE request_id=%s"+
                    (" FOR UPDATE" if lock else ""),(request_id,))
        return result[0] if result else None

    def receive(self, conn, *, code, request_id, order, employee_id, note, lines):
        receipt_id=execute(conn,"INSERT INTO goods_receipts(code,order_id,store_id,received_by,request_id,note,accepted_amount) "
                           "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                           (code,order["id"],order["store_id"],employee_id,request_id,note,
                            sum(x["accepted_quantity"]*x["unit_cost"] for x in lines)))
        for line in lines:
            execute(conn,"INSERT INTO goods_receipt_lines(receipt_id,ingredient_id,accepted_quantity,damaged_quantity,missing_quantity,unit_cost) "
                    "VALUES(%s,%s,%s,%s,%s,%s)",(receipt_id,line["ingredient_id"],line["accepted_quantity"],
                    line["damaged_quantity"],line["missing_quantity"],line["unit_cost"]))
            if line["accepted_quantity"]:
                execute(conn,"UPDATE inventory_ingredients SET on_hand=on_hand+%s WHERE id=%s",
                        (line["accepted_quantity"],line["ingredient_id"]))
                execute(conn,"INSERT INTO inventory_movements(store_id,ingredient_id,employee_id,kind,quantity,on_hand_delta,"
                        "reserved_delta,idempotency_key,reference_code,note) VALUES(%s,%s,%s,'RECEIVE',%s,%s,0,%s,%s,%s)",
                        (order["store_id"],line["ingredient_id"],employee_id,line["accepted_quantity"],line["accepted_quantity"],
                         f"goods-receipt:{receipt_id}:{line['ingredient_id']}",code,note))
            execute(conn,"UPDATE purchase_order_lines SET received_quantity=received_quantity+%s,damaged_quantity=damaged_quantity+%s "
                    "WHERE order_id=%s AND ingredient_id=%s",
                    (line["accepted_quantity"],line["damaged_quantity"],order["id"],line["ingredient_id"]))
        remaining=rows(conn,"SELECT COUNT(*) AS n FROM purchase_order_lines WHERE order_id=%s "
                       "AND received_quantity+damaged_quantity<quantity",(order["id"],))[0]["n"]
        execute(conn,"UPDATE purchase_orders SET status=%s WHERE id=%s",
                ("PARTIALLY_RECEIVED" if remaining else "RECEIVED",order["id"]))
        return receipt_id

    def create_payable(self, conn, *, receipt_id, order, amount, due_date):
        return execute(conn,"INSERT INTO supplier_payables(receipt_id,supplier_id,store_id,amount,due_date) VALUES(%s,%s,%s,%s,%s)",
                       (receipt_id,order["supplier_id"],order["store_id"],amount,due_date))

    def list_payables(self, conn, store_id):
        return rows(conn,"SELECT p.*,s.name AS supplier_name,r.code AS receipt_code,"
                    "a.approved_by,a.approved_at,a.note AS approval_note FROM supplier_payables p "
                    "JOIN suppliers s ON s.id=p.supplier_id JOIN goods_receipts r ON r.id=p.receipt_id "
                    "LEFT JOIN supplier_payable_approvals a ON a.payable_id=p.id "
                    "WHERE p.store_id=%s ORDER BY p.status,p.due_date,p.id",(store_id,))

    def payable(self, conn, payable_id, *, lock=False):
        result=rows(conn,"SELECT * FROM supplier_payables WHERE id=%s"+(" FOR UPDATE" if lock else ""),(payable_id,))
        return result[0] if result else None

    def payable_approval(self, conn, payable_id):
        result=rows(conn,"SELECT payable_id,approved_by,approved_at,note "
                    "FROM supplier_payable_approvals WHERE payable_id=%s",(payable_id,))
        return result[0] if result else None

    def approve_payable(self, conn, payable_id, approver_id, note):
        return execute(conn,"INSERT INTO supplier_payable_approvals(payable_id,approved_by,note) "
                       "VALUES(%s,%s,%s)",(payable_id,approver_id,note))

    def pay(self, conn, payable_id, employee_id, method):
        return execute(conn,"UPDATE supplier_payables SET paid_amount=amount,status='PAID',paid_at=UTC_TIMESTAMP(),"
                       "paid_by=%s,payment_method=%s WHERE id=%s AND status='UNPAID'",(employee_id,method,payable_id))
