"""Sender-style templates: data, not code (README 4.7).

A matching template's patterns (capture group 1) are tried first for payee, reference, account and balance; misses fall back to `parse.py`. Amount and direction always come from the fallback, so a template can only lose detail, never the payment.

When a bank rewords its alerts, edit a row here (bump `version`) and add the message to `tests/parser_table.py`.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Template:
    id: str
    # Bumped whenever the patterns of this row change.
    version: int
    label: str
    # Selects the template.
    match: str
    # Any of `payee`, `reference`, `account`, `balance`.
    fields: dict[str, str] = field(default_factory=dict)


# Bumped on every change to the list below.
TEMPLATES_VERSION = 1

_REF = r'(?:UPI(?:\s*Ref(?:\s*No)?)?|Ref(?:\s*No)?)[\s:.#-]*(\d{9,12})'

TEMPLATES: tuple[Template, ...] = (
    Template(
        'hdfc-sent', 1, 'HDFC Bank: "Sent Rs.X From HDFC Bank A/C ... To NAME On dd/mm/yy Ref N"',
        r'^\s*sent\s+rs\.?\s*[\d,.]+\s+from\s+hdfc\s+bank',
        {'payee': r'\bto\s+(.+?)\s+on\s+\d', 'reference': r'\bref\s*(?:no)?[\s:.#-]*(\d{9,12})'},
    ),
    Template(
        'hdfc-received', 1, 'HDFC Bank: "Received Rs.X in your HDFC Bank A/c ... from VPA ..."',
        r'^\s*received\s+rs\.?\s*[\d,.]+\s+in\s+your\s+hdfc\s+bank',
        {'payee': r'\bfrom\s+(?:vpa\s+)?(\S+@[\w.\-]+|.+?)(?=\s+on\s|\s*\(|\.\s|$)', 'reference': _REF},
    ),
    Template(
        'hdfc-upi', 1, 'HDFC Bank: "Rs.X debited from a/c ... to VPA ..." and "credited to a/c ... by a/c linked to VPA ..."',
        r'^\s*rs\.?\s*[\d,.]+\s+(?:debited\s+from|credited\s+to)\s+a/c\b.*\bvpa\b',
        {'payee': r'\bvpa\s+(\S+?)(?=[\s(.]*(?:\(|upi|ref|$))', 'reference': _REF},
    ),
    Template(
        'hdfc-card', 1, 'HDFC Bank card: "Spent Rs.X On HDFC Bank Card xx1234 At MERCHANT On 2026-10-18:18:42:07"',
        r'^\s*spent\s+rs\.?\s*[\d,.]+\s+on\s+hdfc\s+bank',
        {'payee': r'\bat\s+(.+?)\s+on\s+\d{2,4}-?\d{2}', 'account': r'card\s*[x*]*(\d{4})'},
    ),
    Template(
        'icici-acct-debit', 1, 'ICICI Bank: "Acct XX123 debited for Rs X on dd-Mon-yy; NAME credited. UPI:N"',
        r'icici\s+bank\s+acct\b.*\bdebited\s+for\b',
        {'payee': r';\s*(.+?)\s+credited\b', 'reference': r'\bupi[:\s]+(\d{9,12})', 'account': r'acct\s*[x*]*(\d{3,4})'},
    ),
    Template(
        'icici-acct-credit', 1, 'ICICI Bank: "Acct XX123 credited with Rs X on dd-Mon-yy from NAME. UPI:N"',
        r'icici\s+bank\s+acct\b.*\bcredited\s+with\b',
        {'payee': r'\bfrom\s+(.+?)\.\s*upi', 'reference': r'\bupi[:\s]+(\d{9,12})', 'account': r'acct\s*[x*]*(\d{3,4})'},
    ),
    Template(
        'icici-card', 1, 'ICICI Bank card: "INR X spent using ICICI Bank Card XX1234 on dd-Mon-yy on MERCHANT. Avl Limit: ..."',
        r'spent\s+using\s+icici\s+bank\s+card',
        {'payee': r'\d{2,4}\s+on\s+([a-z].*?)\.\s*(?:avl|$)', 'account': r'card\s*[x*]*(\d{4})'},
    ),
    Template(
        'sbi-upi', 1, 'SBI UPI: "Dear UPI user A/C X1234 debited by 450.0 on date 18Oct26 trf to NAME Refno N"',
        r'dear\s+upi\s+user\b.*\b(?:debited|credited)\s+by\b',
        {'payee': r'\btrf\s+(?:to|from)\s+(.+?)\s+ref\s*no', 'reference': r'\bref\s*no[\s:.]*(\d{9,12})', 'account': r'a/c\s*[x*]*(\d{3,4})'},
    ),
    Template(
        'sbi-card', 1, 'SBI Card: "Rs.X spent on your SBI Credit Card ending 1234 at MERCHANT on dd/mm/yy"',
        r'spent\s+on\s+your\s+sbi\s+(?:credit\s+)?card',
        {'payee': r'\bat\s+(.+?)\s+on\s+\d', 'account': r'ending\s*(\d{4})'},
    ),
    Template(
        'axis-upi', 1, 'Axis Bank: "INR X debited A/c no. XX1234 dd-mm-yy, hh:mm:ss UPI/P2M/N/MERCHANT"',
        r'\bupi/p2[amp]/\d{9,12}/',
        {
            'payee': r'\bupi/p2[amp]/\d{9,12}/([^/\n]+?)(?=\s+(?:sms|not|if|call|avl)\b|\s*$|\.)',
            'reference': r'\bupi/p2[amp]/(\d{9,12})',
            'account': r'a/c\s*no\.?\s*[x*]*(\d{3,4})',
        },
    ),
    Template(
        'neft-imps-credit', 1, 'NEFT / IMPS / RTGS credit: "credited with INR X ... by NEFT-UTR-SENDER-NOTE"',
        r'\b(?:neft|imps|rtgs)[-/\s]',
        {
            'payee': r'\b(?:neft|imps|rtgs)[-/][a-z0-9]+[-/]([^-/]+?)(?=[-/]|\.\s|\s+avl|\s*$)',
            'reference': r'\b(?:neft|imps|rtgs)(?:[-/\s]+(?:ref(?:\s*no)?[\s.:]*)?)((?=[a-z]*\d)[a-z0-9]{9,22})',
        },
    ),
)
