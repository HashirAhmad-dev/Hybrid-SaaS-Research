# FUNSD_GOLD.md

How the partial PII gold list for the FUNSD real-scan subset was derived (task F5; decision D-021). Code: `evaluation/funsd_subset.py`. The rules were fixed before any model was scored on FUNSD and were never changed after.

## Source

FUNSD (Jaume et al., 2019): 199 real scanned forms from RVL-CDIP, with word boxes labelled header, question, answer or other, and links from each question to its answers. FUNSD has no PII labels. Images stay on `D:/datasets/funsd/` and are never committed (their copyright belongs to the RVL-CDIP sources).

## Rule

1. Take every linked question to answer pair.
2. Normalise the question text: lower case, keep letters and spaces only, collapse spaces.
3. If the normalised question equals one of these field names, the answer text becomes a gold entity of that type:

| Type | Question texts that count |
|---|---|
| PERSON | name, to, from, cc, attn, attention, approved by, submitted by, requested by, reported by, prepared by, authorized by, authorised by, contact, sender |
| PHONE | phone, telephone, tel, fax, fax no, fax number, phone no, phone number, telephone no, telephone number |
| ADDRESS | address |
| EMAIL | email, e mail |
| DOB | date of birth, birth date, birthdate |

4. A PERSON answer without digits that lists several names separated by commas becomes one PERSON entity per name.
5. Everything else on the form is not in the gold.

## Result

199 forms, 438 entities (PERSON 365, PHONE 63, ADDRESS 10, no EMAIL or DOB found), 90 forms with no derived field (D-021 addendum).

## What this gold can and cannot support

- Precision on FUNSD is a lower bound: a model that finds a real name in free text, or in a field not listed above, is counted as a false positive.
- Recall covers only the derived fields.
- Known noise is kept as is: "to" and "from" answers that are departments, job titles or postal addresses are counted as PERSON.
- FUNSD is reported as its own subset and never pooled with the synthetic v1 and v2 corpora.
