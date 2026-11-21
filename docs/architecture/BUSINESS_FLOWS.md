# In-scope business flows

## Stores and employees

Stores scope employees, machines, menu data, and POS operations. Employee profiles and store assignments store personnel information and cross-store access. Management actions are recorded in `management_audit`.

## Customers, accounts, and wallet

A customer owns an account. `account_transactions` records top-ups, promotional credits, and usage payments. `promotions` stores general store-level top-up offers. The reduced project does not award points or use member tiers.

## Machines, sessions, and invoices

An employee starts a usage session for a customer on a machine. Ending the session produces an invoice. Sessions, invoices, and account transactions preserve the usage and payment history. `machine_room_types` classifies machines by room type.

## Menu and POS

Menu categories contain menu items. A customer places an order during a usage session. `menu_orders` and `menu_order_items` store the order and its lines. `menu_order_pricing` stores the applied POS offer and final amount. Active POS offers support BOGO and drink discounts. `pos_order_reversals` stores cancellation or refund requests and decisions.

## Customer email and security

Email tokens and the mail outbox support customer activation and recovery flows. `customer_security_audit` records security events for customer accounts.
