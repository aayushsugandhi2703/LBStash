"""The parser's test table (README 4.7): message in, fields out. Every bank rewording or new template adds a row
here, so a pattern change cannot silently break another bank. Digits and names are hidden (XX1234, ramesh@okaxis).

Amounts are paise. Unless a row says otherwise: payee, reference, account_last4 and balance_after_minor are None,
reversal and weak_parse are False, and the payment time is `received_at`.
"""

from dataclasses import dataclass
from datetime import datetime

RECEIVED_AT = '2026-10-18T18:42:07+05:30'
TZ = 'Asia/Kolkata'


def ist(s: str) -> datetime:
    """A wall-clock time written in a message (IST) as the real instant."""
    return datetime.fromisoformat(s.replace(' ', 'T') + '+05:30')


@dataclass(frozen=True)
class Expected:
    type: str
    amount_minor: int
    payee: str | None = None
    reference: str | None = None
    account_last4: str | None = None
    balance_after_minor: int | None = None
    reversal: bool = False
    weak_parse: bool = False
    # Default = received_at.
    at: datetime | None = None
    # Template id that must have matched (None = generic fallback only); unchecked when the row says `...`.
    template: object = ...


@dataclass(frozen=True)
class Row:
    name: str
    text: str
    received_at: str | None = None
    expect: Expected | None = None
    ignored: str | None = None
    unreadable: str | None = None
    hints: dict | None = None


def out(amount_minor: int, **e) -> Expected:
    return Expected('debit', amount_minor, **e)


def inn(amount_minor: int, **e) -> Expected:
    return Expected('credit', amount_minor, **e)


TABLE: list[Row] = [
    # HDFC
    Row('HDFC UPI debit to a VPA', 'Rs.450.00 debited from a/c **1234 on 18-10-26 to VPA ramesh@okaxis (UPI Ref No 123456789012). Not you? Call 18002586161',
        expect=out(45000, payee='ramesh@okaxis', reference='123456789012', account_last4='1234', template='hdfc-upi')),
    Row('HDFC UPI credit from a VPA', 'Rs. 50000.00 credited to a/c XXXXXX1234 on 18-10-26 by a/c linked to VPA employer@icici (UPI Ref No 234567890123).',
        expect=inn(5000000, payee='employer@icici', reference='234567890123', account_last4='1234', template='hdfc-upi')),
    Row('HDFC "Sent" wording with a name and an earlier date (noon of that day)', 'Sent Rs.1250.00 From HDFC Bank A/C *1234 To SWIGGY On 17/10/26 Ref 345678901234 Not You? Call 18002586161 To Block UPI',
        expect=out(125000, payee='SWIGGY', reference='345678901234', account_last4='1234', at=ist('2026-10-17 12:00:00'), template='hdfc-sent')),
    Row('HDFC "Received" wording', 'Received Rs.2,500.00 in your HDFC Bank A/c XX1234 from VPA friend@oksbi on 18-10-26 (UPI 456789012345)',
        expect=inn(250000, payee='friend@oksbi', reference='456789012345', account_last4='1234', template='hdfc-received')),
    Row('HDFC debit card with yyyy-mm-dd:time and Avl bal', 'Spent Rs.320.00 On HDFC Bank Card x1234 At ZOMATO On 2026-10-18:18:42:07.Avl bal Rs.12,345.67',
        expect=out(32000, payee='ZOMATO', account_last4='1234', balance_after_minor=1234567, at=ist('2026-10-18 18:42:07'), template='hdfc-card')),
    Row('HDFC NEFT salary, lakh commas, Avl bal', 'HDFC Bank: Rs. 85,000.00 credited to a/c XX1234 on 01-10-26 by NEFT-HDFCN52026100112345-ACME TECHNOLOGIES PVT LTD-SALARY SEP 2026. Avl bal Rs.1,23,456.78',
        expect=inn(8500000, payee='ACME TECHNOLOGIES PVT LTD', reference='HDFCN52026100112345', account_last4='1234', balance_after_minor=12345678, at=ist('2026-10-01 12:00:00'), template='neft-imps-credit')),
    Row('HDFC credit with a reference but no payee', 'Rs. 10000.00 credited to a/c XX1234 on 18-10-26 (UPI Ref No 667788990011).',
        expect=inn(1000000, reference='667788990011', account_last4='1234', template=None)),
    Row('HDFC debit with the rupee sign, no template', '₹1,234.50 debited from a/c XX4321 on 18-10-26 to VPA bigbasket@ybl',
        expect=out(123450, payee='bigbasket@ybl', account_last4='4321', template=None)),
    Row('Credit card bill payment received', 'Payment of Rs.5,000.00 received towards your HDFC Bank Credit Card XX1234 on 18-10-26',
        expect=inn(500000, account_last4='1234', weak_parse=True)),

    # ICICI
    Row('ICICI account debit (payee after the semicolon)', 'ICICI Bank Acct XX123 debited for Rs 450.00 on 18-Oct-26; RAMESH KUMAR credited. UPI:123456789012. Call 18002662 for dispute or SMS BLOCK 123 to 9215676766.',
        expect=out(45000, payee='RAMESH KUMAR', reference='123456789012', account_last4='123', template='icici-acct-debit')),
    Row('ICICI account credit', 'ICICI Bank Acct XX123 credited with Rs 50,000.00 on 18-Oct-26 from ACME CORP. UPI:234567890123. Call 18002662 for dispute.',
        expect=inn(5000000, payee='ACME CORP', reference='234567890123', account_last4='123', template='icici-acct-credit')),
    Row('ICICI card spend; Avl Limit is not the balance', 'INR 1,250.00 spent using ICICI Bank Card XX1234 on 18-Oct-26 on AMAZON PAY INDIA. Avl Limit: INR 98,750.00. If not you, call 18002662',
        expect=out(125000, payee='AMAZON PAY INDIA', account_last4='1234', template='icici-card')),
    Row('ICICI debit with a reference and no payee (fallback only)', 'ICICI Bank Acct XX123 debited Rs. 99.00 on 18-Oct-26. UPI:345678901234',
        expect=out(9900, reference='345678901234', account_last4='123', template=None)),

    # SBI
    Row('SBI UPI debit, "450.0" with no currency sign, date as 18Oct26', 'Dear UPI user A/C X1234 debited by 450.0 on date 18Oct26 trf to RAMESH KUMAR Refno 123456789012. If not u? call 1800111109. -SBI',
        expect=out(45000, payee='RAMESH KUMAR', reference='123456789012', account_last4='1234', template='sbi-upi')),
    Row('SBI UPI credit', 'Dear UPI user A/C X1234 credited by Rs 2000.00 on date 18Oct26 trf from AMIT VERMA Ref no 567890123456. -SBI',
        expect=inn(200000, payee='AMIT VERMA', reference='567890123456', account_last4='1234', template='sbi-upi')),
    Row('SBI UPI debit, mixed-case payee, earlier date', 'Dear UPI user A/C X1234 debited by Rs.60.00 on date 17Oct26 trf to Chai Wala Refno 700011223344',
        expect=out(6000, payee='Chai Wala', reference='700011223344', account_last4='1234', at=ist('2026-10-17 12:00:00'), template='sbi-upi')),
    Row('SBI credit card spend, dd/mm/yy', 'Rs.1,250.00 spent on your SBI Credit Card ending 1234 at AMAZON on 18/10/26. Trxn. not done by you? Report at 1800123456',
        expect=out(125000, payee='AMAZON', account_last4='1234', template='sbi-card')),
    Row('SBI ATM withdrawal with a time and Avl Bal (weak: no payee)', 'Rs.5,000 withdrawn from SBI ATM using card ending 1234 on 18-10-26 18:30. Avl Bal Rs.20,100.55',
        expect=out(500000, account_last4='1234', balance_after_minor=2010055, at=ist('2026-10-18 18:30:00'), weak_parse=True, template=None)),

    # Axis
    Row('Axis UPI debit to a merchant', 'INR 450.00 debited\nA/c no. XX1234\n18-10-26, 18:42:07\nUPI/P2M/123456789012/SWIGGY\nNot you? SMS BLOCK UPI to 7308080808',
        expect=out(45000, payee='SWIGGY', reference='123456789012', account_last4='1234', at=ist('2026-10-18 18:42:07'), template='axis-upi')),
    Row('Axis UPI credit, dd-mm-yyyy and a morning time', 'INR 50000.00 credited to A/c no. XX1234 18-10-2026 09:15:00 through UPI/P2A/234567890123/RAMESH KUMAR. Axis Bank',
        expect=inn(5000000, payee='RAMESH KUMAR', reference='234567890123', account_last4='1234', at=ist('2026-10-18 09:15:00'), template='axis-upi')),
    Row('Axis card spend with no merchant separator (weak parse)', 'Spent INR 1250 Axis Bank Card no. XX1234 18-10-26 18:42:07 IST AMAZON Avl Limit INR 98750',
        expect=out(125000, account_last4='1234', at=ist('2026-10-18 18:42:07'), weak_parse=True, template=None)),

    # other wording, formats and amounts
    Row('Salary credit with lakh commas and Avl Bal, no payee', 'Your a/c XX1234 is credited with Rs.1,25,000.00 on 01-10-26. Info: SALARY. Avl Bal Rs.1,40,321.50',
        expect=inn(12500000, account_last4='1234', balance_after_minor=14032150, at=ist('2026-10-01 12:00:00'), weak_parse=True)),
    Row('RTGS credit with paise', 'Acct XX9876 credited INR 3,00,000.50 on 18-Oct-26 by RTGS-SBIN12345678901-INFOSYS LTD',
        expect=inn(30000050, payee='INFOSYS LTD', reference='SBIN12345678901', account_last4='9876', template='neft-imps-credit')),
    Row('IMPS credit with the sender in plain words', 'Dear Customer, INR 12,000.00 credited to your A/c XX1234 on 18-Oct-26 via IMPS Ref no 612345678901 from RAHUL SHARMA.',
        expect=inn(1200000, payee='RAHUL SHARMA', reference='612345678901', account_last4='1234', template='neft-imps-credit')),
    Row('"Rs" glued to the number, no date', 'Rs450 debited from a/c XX1234 to ZOMATO UPI Ref 112233445566',
        expect=out(45000, payee='ZOMATO', reference='112233445566', account_last4='1234')),
    Row('dd/mm/yyyy with "at hh:mm"', 'Rs 3,499.00 debited from A/c XX1234 on 15/10/2026 at 21:05 to PAYTM MERCHANT. UPI Ref 998877665544',
        expect=out(349900, payee='PAYTM MERCHANT', reference='998877665544', account_last4='1234', at=ist('2026-10-15 21:05:00'))),
    Row('dd-Mon-yy with a 12-hour clock', 'Rs 75.00 paid to CHAI POINT via UPI on 18-Oct-26 06:42 PM. Ref no 223344556677',
        expect=out(7500, payee='CHAI POINT', reference='223344556677', at=ist('2026-10-18 18:42:00'))),
    Row('Send to a bare UPI id', 'Rs.300 sent to 9876543210@ybl on 18-10-26. UPI Ref 334455667788',
        expect=out(30000, payee='9876543210@ybl', reference='334455667788')),
    Row('Credit from a person by name', 'You have received Rs 1,000.00 from PRIYA SHARMA on 18-10-26. UPI Ref 445566778899',
        expect=inn(100000, payee='PRIYA SHARMA', reference='445566778899')),
    Row('POS debit with "debited with", merchant before "(POS)"', 'Your a/c XX1234 has been debited with INR 2,150.75 on 18-Oct-26 at BIG BAZAAR (POS). Avl Bal INR 5,000.00',
        expect=out(215075, payee='BIG BAZAAR', account_last4='1234', balance_after_minor=500000)),
    Row('Credit with "UPI:" prefix and "UPI Ref:" later', 'UPI: Rs 100.00 credited to a/c XX1234 on 18-10-26 from VPA mom@oksbi. UPI Ref: 556677889900',
        expect=inn(10000, payee='mom@oksbi', reference='556677889900', account_last4='1234')),
    Row('Fifty paise interest credit (weak parse)', 'Rs.0.50 credited to your a/c XX1234 on 18-10-26 - interest',
        expect=inn(50, account_last4='1234', weak_parse=True)),
    Row('The Setup guide test text', 'Rs 1.00 debited test',
        expect=out(100, weak_parse=True)),
    Row('A date older than 45 days is distrusted: receivedAt wins', 'Rs 200.00 debited from a/c XX1234 on 18-01-26 to VPA old@ybl',
        expect=out(20000, payee='old@ybl', account_last4='1234')),
    Row('A date in the future is distrusted: receivedAt wins', 'Rs 200.00 debited from a/c XX1234 on 28-10-26 to VPA future@ybl',
        expect=out(20000, payee='future@ybl', account_last4='1234')),
    Row('Same message, UTC receivedAt near midnight IST keeps the IST day', 'Rs 80.00 debited from a/c XX1234 on 19-10-26 00:10:30 to VPA late@ybl', received_at='2026-10-18T18:45:00Z',
        expect=out(8000, payee='late@ybl', account_last4='1234', at=ist('2026-10-19 00:10:30'))),

    # reversals, refunds, failures
    Row('Refund credited, with the original reference', 'Refund of Rs.450.00 credited to your a/c XX1234 on 18-10-26 for UPI Ref 123456789012 (txn to SWIGGY).',
        expect=inn(45000, reference='123456789012', account_last4='1234', reversal=True)),
    Row('UPI reversal naming the VPA', 'UPI txn of Rs 450.00 to VPA ramesh@okaxis reversed. UPI Ref 123456789012. Amount credited back to a/c XX1234.',
        expect=inn(45000, payee='ramesh@okaxis', reference='123456789012', account_last4='1234', reversal=True)),
    Row('Failed transaction', 'Transaction of Rs 899.00 at AMAZON failed on 18-10-26. Ref no 876543210987.',
        expect=inn(89900, reference='876543210987', reversal=True)),
    Row('Failed payment that only promises a refund is not a transaction', 'Your UPI payment of Rs 1,200.00 to VPA shop@paytm has failed. Ref 987654321012. Money debited, if any, will be refunded in 3-5 days',
        ignored='not_a_transaction'),

    # OTP (always ignored, even with amounts and "debit" words)
    Row('OTP for a card payment', '123456 is your OTP for transaction of Rs 450.00 at AMAZON. Do not share with anyone. -HDFC Bank', ignored='otp_or_promo'),
    Row('OTP for UPI with validity', 'OTP for UPI transaction of INR 1,200.00 is 482915. Valid for 10 minutes. Never share your OTP. - ICICI Bank', ignored='otp_or_promo'),
    Row('One time password for net banking', 'Dear Customer, 482915 is the One Time Password to login to SBI Online. Valid for 5 mins. Do not share it with anyone.', ignored='otp_or_promo'),
    Row('Verification code that mentions a debit', 'Your verification code is 739201. Rs.10.00 will be debited for activation. Do not disclose.', ignored='otp_or_promo'),
    Row('OTP with a debit amount and no other trigger words', 'Axis Bank: 884213 for Rs.5,000.00 debit at FLIPKART. Valid till 18:50.', ignored='otp_or_promo'),
    Row('Login code', 'Use 5521 as your Axis Bank login code. Valid for 5 minutes.', ignored='otp_or_promo'),

    # promos and non-transactions
    Row('Cashback offer', 'Get 5% cashback up to Rs 100 on UPI payments. Offer valid till 31-10-26. T&C apply.', ignored='otp_or_promo'),
    Row('Loan promo that says "credited"', 'Pre-approved personal loan of Rs 5,00,000 credited instantly! Apply now at hdfcbank.com/loan', ignored='otp_or_promo'),
    Row('Festive offers', 'Dear Customer, enjoy exclusive offers on festive shopping with your HDFC card. Spend Rs 10,000 and win rewards.', ignored='otp_or_promo'),
    Row('Balance enquiry', 'Your a/c XX1234 balance is Rs 12,345.67 as of 18-Oct-26.', ignored='not_a_transaction'),
    Row('Future debit notice', 'Rs 1,250.00 will be debited from your a/c XX1234 on 20-Oct-26 towards EMI.', ignored='not_a_transaction'),
    Row('Credit card statement', 'Your HDFC Credit Card statement for Oct is generated. Total amount due Rs 4,520.00, due date 05-Nov-26.', ignored='not_a_transaction'),
    Row('UPI collect request', 'Ramesh Kumar has requested Rs 500.00 from you on UPI. Approve in your app.', ignored='not_a_transaction'),

    # unreadable (kept encrypted in Needs a look)
    Row('Card use with no direction word', 'Your SBI Debit Card ending 5678 was used for Rs 799.00 at NETFLIX on 18-10-26.',
        unreadable='direction_unclear', hints={'type': 'debit', 'amount_minor': 79900, 'payee': 'NETFLIX'}),
    Row('The ui-spec sample: amount found, direction unclear', 'Txn of INR 1,250.00 on card ending 4821 at AMAZON PAY INDIA, 17-Oct. Avl bal INR 37,591.00. Not you? Call the number on the back of your card.',
        unreadable='direction_unclear', hints={'type': 'debit', 'amount_minor': 125000, 'payee': 'AMAZON PAY INDIA'}),
    Row('Amount but no direction and no hints', 'Rs 450.00 transaction on your a/c XX1234 at 18:42', unreadable='direction_unclear'),
    Row('No amount at all', 'Your a/c ending 4821 has been updated. Please check the app for details.', unreadable='no_amount'),
    Row('Garbage', 'asdf qwer zxcv', unreadable='no_amount'),
    Row('Emoji and noise', '??? 😀 ###', unreadable='no_amount'),
]
