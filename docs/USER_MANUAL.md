# FML Requisition System: User Manual

For everyone who raises, reviews, approves, pays or administers payment requisitions at First Mutual Life. IT staff should read [IT_GUIDE.md](IT_GUIDE.md) instead.

## 1. What the system does

A payment requisition is the request to pay money to someone. The system takes it from the person who raises it, through a reviewer and two or three approvers, to a signed, stamped document that can be downloaded, printed, verified and tracked until it is paid.

```
Initiator  ->  Reviewer  ->  Approver 1  ->  Approver 2  ->  (Senior approver)  ->  Approved  ->  Paid
```

## 2. Roles

Your administrator gives you one or more of these permissions.

| Role | What you can do |
|---|---|
| Initiator | Create requisitions, correct rejected ones, mark approved ones as Paid. |
| Reviewer | Check new requisitions and pass them to approvers or reject them. |
| Approver | Approve or reject reviewed requisitions. |
| Senior approver | The third approval on large amounts (see section 6). |
| Administrator | Everything above, plus users, paying banks, the account list, audit logs and payment reversals. |

## 3. Getting started

1. Open the system address your IT team gave you and choose **Request an account**.
2. Fill in your details and register. You can upload your signature now or later.
3. Wait for the administrator to activate your account and give you permissions. You cannot log in before then.
4. Log in with your corporate email and password.
5. Open your **Profile** and upload a clear picture of your signature (PNG or JPG, dark ink on a white background). **You cannot submit, review or approve until a signature is on file.**

Use the **Dark mode** button at the top to switch the theme. The bell shows your notifications. The search box at the top finds requisitions by number, payee, bank, account number, reason, status or currency.

## 4. Raising a requisition (initiators)

Choose **Create** and fill in the form.

**Paying Bank.** Pick the bank account the money will leave from. The administrator maintains this list. If yours is missing, choose **Other** and type the bank name, account name, account number and SWIFT code.

**Payment Details.**
- In Favor Of: who is being paid.
- Currency: USD, ZWG, ZAR or BWP.
- Bank Name, Branch, Account Number: the payee's bank details.
- Reason for Payment.
- ITF 263: Yes, No or N/A.

**Account Details.** One row per accounting line. Use **Add Item** for more rows.
- Account Name, Account Code and Location are drop-downs filled from the list your administrator uploads. Choosing an Account Name fills in its code and location, which you can still change. If no list has been uploaded yet, these three fields are plain text boxes.
- Department: EB or FIN.
- Details: fills in automatically from your Reason for Payment and holds at most 35 characters. Type your own text to override it.
- Debit or Credit amount. The totals and the number of approvers needed show below the table.

**Supporting Documents.** Attach PDF, PNG or JPG files (invoices, quotes). All files together may not exceed 16 MB. They are attached after the requisition in the merged PDF.

Press **Submit Requisition**. It goes to the reviewers and you get a confirmation. Each person who must act is notified.

### Changing your mind: Recall

Until the first approval is given you can open the requisition and press **Recall**. It leaves the queue and you can edit it and resubmit. Once approval has started, recall is no longer possible.

## 5. Reviewing (reviewers)

Open the requisition from **Pending review** (or the review queue), check the details and documents, add comments, and either pass it on or reject it with a reason. Rejection returns it to the initiator.

## 6. Approving (approvers)

Open it from **Pending approval** and choose **Approve** or **Reject**. A rejection needs a reason.

How many approvals are needed:

| Requisition | Approvals |
|---|---|
| USD below 5,000, or any other currency | 2 |
| USD 5,000 or more | 3 (the third must be a senior approver) |

Each approval stamps your signature, name and the time on the document. When the last approval is given the requisition becomes **Approved**.

## 7. When a requisition is rejected

The initiator sees the rejection reason on the requisition. Two choices are always available until you act:

- **Correct Mistakes** (also shown in the list): edit anything, then **Resubmit**. It starts the review again.
- **Delete**: removes the rejected requisition permanently. You are asked to confirm and this cannot be undone.

## 8. Paid and Not Paid

Every fully approved requisition carries a stamp, on screen, in print and in every download.

- Red **NOT PAID**: approved, payment not yet made. This is the starting state.
- Green **PAID**: the payment has been made.

**Marking Paid.** Only the initiator can do this. Open the requisition and press **Mark as Paid**, then confirm. You cannot undo it yourself.

**If the payment bounces after you marked it Paid:**
1. Open the requisition and expand **Payment was rejected? Request a reversal**.
2. Give the reason and attach a supporting document (for example the bank's rejection notice). Both are required.
3. The administrator is notified and reviews your request on the **Payment reversals** page.
4. If accepted, the administrator sets it back to Not Paid. The reason and date are written on the requisition and you are notified.
5. When the payment finally succeeds, mark it Paid again.

## 9. Downloading and printing

On an approved requisition use **Download** for PDF, Word, Excel or CSV, or **Print View**.

- **Print View** opens exactly the same PDF as the PDF download, with supporting documents attached. Print it from your browser.
- Every format shows the Paid or Not Paid stamp, the payment details laid out in pairs (In Favor Of, Bank, Branch, Account Number, Currency, ITF 263, Date Created, Date Completed), and the signature, name and exact time of everyone involved: initiator, reviewer, each approver and whoever marked it Paid.
- Signature images only appear for people who have uploaded one.
- PDF, Word and Excel carry a **QR code**. CSV carries the same link as text.

### Verifying a document

Scan the QR code with a phone camera, or click it in the PDF, to open the verification page. No login is needed.

- **Verified** (green): the document matches the system's current record. The page shows status, Paid or Not Paid, payee, amount and who signed and when.
- **Not verified** (red): the copy is out of date or has been altered. Do not rely on it.

The page never shows bank account numbers.

## 10. Reports and batches

**Reports** lists requisitions with filters (dates, status, currency and others) and exports to CSV, Excel or PDF.

**Stanbic batches** (reviewers, approvers and administrators). Approved requisitions waiting for payment appear on **Batches**. Select them, check the account name, code and reference for each line, then create the batch and download it as CSV for upload to Stanbic Business Online, or as Excel. Bank codes and branches are filled from the receiving bank name. Known banks: POSB, CABS, Stanchart, ZB, NMB, Stanbic, Nedbank, Agribank, First Capital, Banc ABC, CBZ, Ecobank, FBC, NBS and TN Cyber Bank (also typed as Steward). If a bank is not recognised, enter its code by hand. Files have no heading row, and account numbers carry a leading apostrophe so Excel keeps them as text.

## 11. Administrator tasks

Open the admin menu in the sidebar.

**Users.** New registrations wait here, inactive. Open a user to set their role and tick the permissions: initiate, review, approve, senior approver. Activate or deactivate accounts, or create users directly.

**Paying banks.** Download the Excel template (Bank Name, Account Name, Account Number, Currency Code), fill it in and upload it. Rows already present are updated, new ones added. Disable a bank to hide it from the drop-down without losing history.

**Account list.** Download the template (Account Name, Account Code, Location), fill it in and upload it. On every upload you must choose:
- **Add to the existing list**: new rows are added and rows already there are skipped.
- **Replace the whole list**: all current rows are deleted first, with an extra confirmation.

Keep codes as text so leading zeros survive. Existing requisitions keep the values they were saved with.

**Payment reversals.** Lists initiators' requests with their reason. Open the requisition to read the supporting document, add an optional note, and press **Mark as Not Paid**. The initiator is notified and can mark it Paid again later.

**Audit logs.** A record of who did what and when: logins, submissions, approvals, rejections, deletions, uploads, Paid and Not Paid changes. Filter by user or action.

## 12. Assistant

The **Assistant** page answers questions about how the system works and about the company, using live system data. It is a guide, not an authority. Check important figures on the requisition itself.

## 13. Troubleshooting

| Problem | What to do |
|---|---|
| I cannot log in after registering | Your account has not been activated. Ask the administrator. |
| Submit or Approve is disabled | Upload your signature in your Profile. |
| Account Name, Code and Location are text boxes | No account list has been uploaded. Ask the administrator. |
| My paying bank is not in the list | Choose Other and type the details, or ask the administrator to add it. |
| I cannot recall my requisition | Approval has already started. Ask the approver to reject it, then correct and resubmit. |
| I marked Paid by mistake | Request a reversal with a reason and a supporting document (section 8). |
| A signature image is missing from a download | That person has no signature on file, or it needs uploading again. |
| The QR page says Not verified | The requisition changed after the copy was made. Download a fresh copy. |
| An upload to Paying banks or Account list is refused | The first row must be the template headings, required columns must be filled, and the file must be .xlsx. The page lists the failing rows. |
