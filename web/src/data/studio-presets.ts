/**
 * Studio scenarios. Each has a question with a known answer, so the page can show whether the answer survived
 * compression and whether it survived plain truncation to the same size. Texts are built from small templates
 * to keep this file short; they are fictional.
 */

export type Preset = {
  id: string
  name: string
  blurb: string
  question: string
  answer: string
  /** How plain truncation would cut this text: keep the start (documents, tool output) or the end (chat). */
  baseline: "head" | "tail"
  keep: number
  mono?: boolean
  text: string
}

/* ------------------------------------------------------------------ a support chat over six months */

const CHAT_FILLER: [string, string][] = [
  ["How do I download last month's statement as a PDF?", "Open Statements, pick the month and choose Download PDF. It includes every transaction and fee."],
  ["The app logs me out every time I switch to another app.", "That was a bug in version 4.2.1. Updating to 4.2.3 keeps your session for up to 30 days."],
  ["Can I set a monthly spending limit on the card?", "Yes. Go to Card settings, then Limits, and set a monthly cap. You get a notification at 80 percent."],
  ["Why was I charged a foreign transaction fee in March?", "The merchant was billed in US dollars. Your plan charges 1.5 percent on foreign currency, shown on the statement."],
  ["I want to turn on two-factor authentication.", "Open Security, choose Two-step verification and scan the code with your authenticator app."],
  ["Does the premium plan include airport lounge access?", "Premium includes four lounge visits a year at partner lounges. The list is in the Benefits tab."],
  ["My UPI payment failed but the money left my account.", "Failed UPI payments are reversed automatically within 48 hours. Yours was reversed on the next working day."],
  ["Can I add my sister as an authorised user?", "You can add up to two authorised users from Account, Members. They get their own card with a separate limit."],
  ["How do reward points convert to cash?", "Every 100 points convert to 25 rupees. You can redeem from Rewards once you have at least 500 points."],
  ["The statement shows a duplicate charge from a grocery store.", "The second entry was a pre-authorisation hold. It dropped off after three days and was never charged."],
  ["Is there a way to export transactions to a spreadsheet?", "Yes. In Statements choose Export, then CSV. The export covers up to 12 months at a time."],
  ["Can I change the date my bill is due?", "You can move the due date once every six months from Billing, Due date. The new date applies from next cycle."],
]

function chatText() {
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
  const sessions: string[] = []
  let day = 3
  const add = (when: string, turns: [string, string][]) => {
    sessions.push(`Session ${sessions.length + 1}, ${when}\n${turns.map(([user, agent]) => `User: ${user}\nAgent: ${agent}`).join("\n")}`)
  }
  add("Jan 3", [["Hi, I just opened the account. Please ship everything to my office in Connaught Place, New Delhi.", "Done. Your shipping address is set to the Connaught Place office in New Delhi."], CHAT_FILLER[4]])
  for (let i = 0; i < 26; i++) {
    const month = months[Math.min(5, Math.floor(i / 5))]
    day = (day + 7) % 27 + 1
    if (i === 13) {
      add(`${month} ${day}`, [["I moved to Pune last month. Please ship any new card or letters to my new home: 14 Lane 5, Koregaon Park, Pune.", "Updated. Your shipping address is now 14 Lane 5, Koregaon Park, Pune. The Delhi office address is removed."], CHAT_FILLER[(i + 3) % CHAT_FILLER.length]])
      continue
    }
    add(`${month} ${day}`, [CHAT_FILLER[i % CHAT_FILLER.length], CHAT_FILLER[(i * 5 + 2) % CHAT_FILLER.length]])
  }
  add("Jun 27", [["My wallet was stolen at the station this morning and the card was in it.", "I have blocked the card. A replacement will be issued today."], CHAT_FILLER[1]])
  return sessions.join("\n\n")
}

/* ------------------------------------------------------------------ help-centre search results */

const PASSAGES: [string, string][] = [
  ["Plans and pricing", "Teams can choose a monthly or an annual plan. Annual plans are billed once a year and cost the same as ten months of the monthly plan. Prices exclude local taxes, which are added at checkout."],
  ["Adding and removing seats", "Admins add seats from Settings, then Members. New seats are billed pro rata for the rest of the billing period. Removed seats stay active until the period ends."],
  ["Single sign-on", "SSO with SAML 2.0 is available on the Business plan. Okta, Azure AD and Google Workspace are supported. Admins can require SSO for every member of the workspace."],
  ["Data retention", "Workspace data is kept while the subscription is active. After cancellation, data is kept for 90 days and then deleted permanently from every region."],
  ["Exporting your data", "Owners can export every project, comment and file as a ZIP archive from Settings, then Export. Large exports are prepared in the background and emailed when ready."],
  ["API rate limits", "The REST API allows 600 requests per minute per workspace. Bursts above the limit receive HTTP 429 with a Retry-After header."],
  ["Refunds for monthly plans", "Monthly plans can be refunded within 14 days of the first charge if the workspace has fewer than five members. Renewals of monthly plans are not refundable."],
  ["Invoices and receipts", "Invoices are emailed to the billing contact on each charge. Past invoices can be downloaded as PDF from Billing, then History, for up to seven years."],
  ["Changing the billing contact", "Only the workspace owner can change the billing contact. The new contact receives every invoice from the next charge onward."],
  ["Security and compliance", "The service is SOC 2 Type II audited every year. Data is encrypted at rest with AES-256 and in transit with TLS 1.2 or later."],
  ["Payment methods", "Cards from Visa, Mastercard and American Express are accepted. Annual plans over 5,000 dollars can also be paid by bank transfer against an invoice."],
  ["Refunds for annual plans", "Annual plans can be refunded in full within 30 days of purchase. After 30 days, unused months are credited to the workspace rather than refunded to the card."],
  ["Downgrading a plan", "Downgrades take effect at the end of the current billing period. Features above the new plan are disabled, but no data is deleted."],
  ["Student and nonprofit discounts", "Verified students get the Pro plan free for a year. Registered nonprofits receive 50 percent off any annual plan after a short review."],
  ["Workspace ownership", "The owner can transfer ownership to any admin from Settings, then Ownership. The previous owner becomes an admin after the transfer."],
  ["Service status", "Live status and past incidents are published on the status page. Customers on the Business plan get a 99.9 percent uptime commitment with service credits."],
]

const passagesText = () => PASSAGES.map(([title, body], i) => `[${i + 1}] ${title}\n${body}`).join("\n\n")

/* ------------------------------------------------------------------ a failing CI run */

function logText() {
  const lines: string[] = [
    "2026-10-09T08:14:02Z Run actions/checkout@v4",
    "2026-10-09T08:14:03Z Syncing repository: acme/billing-service",
    "2026-10-09T08:14:09Z Run actions/setup-python@v5 with python-version 3.12",
    "2026-10-09T08:14:21Z Installing dependencies from requirements-dev.txt",
  ]
  const deps = ["fastapi==0.115.2", "pydantic==2.9.2", "sqlalchemy==2.0.36", "httpx==0.27.2", "pytest==8.3.3", "pytest-cov==5.0.0", "freezegun==1.5.1", "stripe==11.1.0"]
  deps.forEach((dep) => lines.push(`2026-10-09T08:14:3${lines.length % 10}Z Successfully installed ${dep}`))
  lines.push("2026-10-09T08:15:02Z Run pytest -q --cov=billing", "============================= test session starts ==============================", "platform linux -- Python 3.12.7, pytest-8.3.3", "collected 213 items", "")
  const modules = ["test_accounts", "test_auth", "test_customers", "test_discounts", "test_exports", "test_invoices", "test_payments", "test_plans", "test_refunds", "test_webhooks"]
  const cases = ["creates_record", "rejects_missing_fields", "updates_in_place", "handles_pagination", "serialises_dates", "respects_permissions", "retries_on_timeout", "rounds_amounts"]
  let n = 0
  modules.forEach((module, m) => {
    cases.forEach((name) => {
      n++
      lines.push(`tests/${module}.py::test_${name} PASSED${" ".repeat(4)}[${String(Math.round((n / 213) * 100)).padStart(3)}%]`)
      if (n % 3 === 0) lines.push("  DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version.")
    })
    if (m === 5) {
      lines.push(
        "tests/test_invoices.py::test_invoice_total_with_tax FAILED      [ 30%]",
        "",
        "=================================== FAILURES ===================================",
        "_________________________ test_invoice_total_with_tax __________________________",
        "    def test_invoice_total_with_tax(make_invoice):",
        "        invoice = make_invoice(lines=[(\"seat\", 12, 900)], region=\"EU\")",
        ">       assert invoice.total() == 13_068",
        "billing/invoices.py:88: in total",
        "    rate = TAX_TABLE[self.region][self.customer.currency]",
        "E   KeyError: 'currency'",
        "E   The customer fixture no longer sets a currency since commit 4f2c9a1 (\"move currency to account\").",
        "",
      )
    }
  })
  lines.push(
    "---------- coverage: platform linux, python 3.12.7 ----------",
    "TOTAL                                   4127    291    93%",
    "=========================== short test summary info ============================",
    "FAILED tests/test_invoices.py::test_invoice_total_with_tax",
    "============ 1 failed, 80 passed, 27 warnings in 41.27s ============",
    "2026-10-09T08:15:48Z Error: Process completed with exit code 1.",
  )
  return lines.join("\n")
}

export const PRESETS: Preset[] = [
  { id: "chat", name: "Support chat", blurb: "Six months of conversations with one customer", question: "Where should the replacement card be shipped?", answer: "Koregaon Park", baseline: "tail", keep: 0.2, text: chatText() },
  { id: "rag", name: "Search results", blurb: "Sixteen help-centre articles for one question", question: "What is the refund window for annual plans?", answer: "30 days", baseline: "head", keep: 0.25, text: passagesText() },
  { id: "log", name: "CI log", blurb: "A test run with one failure in the middle", question: "Why did the build fail?", answer: "KeyError: 'currency'", baseline: "head", keep: 0.2, mono: true, text: logText() },
  { id: "own", name: "Your own text", blurb: "Paste anything: a document, a thread, a log", question: "", answer: "", baseline: "head", keep: 0.3, text: "" },
]
