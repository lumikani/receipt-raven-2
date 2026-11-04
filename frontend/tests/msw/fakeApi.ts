import { http, HttpResponse } from 'msw';

import type {
  AccountRolesResponse,
  AccountShareDefault,
  AccountShareDefaultRequest,
  ClassificationRule,
  ClassificationRuleRequest,
  Job,
  LedgerAccount,
  Receipt,
  ReceiptRequest,
  ReceiptSummary,
  SetRuleEnabledRequest,
} from '@/api/generated/model';
import { normalizeName } from '@/lib/classification';

/**
 * An in-memory Receipt Raven API, so a test can approve a receipt or retry a
 * job and see the pages change the way they would against the real backend.
 * `resetFakeApi` runs after every test.
 */
interface State {
  receipts: Receipt[];
  jobs: Job[];
  nextId: number;
  ledgerRejection: string | null;
  approvals: { receiptId: number; body: ReceiptRequest }[];
  uploads: { name: string; type: string; size: number }[];
  rules: ClassificationRule[];
  shareDefaults: AccountShareDefault[];
  accountRoles: AccountRolesResponse;
  createdRules: ClassificationRuleRequest[];
  updatedRules: { ruleId: number; body: ClassificationRuleRequest }[];
  deletedRuleIds: number[];
  enabledChanges: { ruleId: number; enabled: boolean }[];
  shareDefaultUpserts: AccountShareDefaultRequest[];
  deletedShareDefaults: string[];
  reclassifications: number[];
}

const fresh = (): State => ({
  receipts: [],
  jobs: [],
  nextId: 1,
  ledgerRejection: null,
  approvals: [],
  uploads: [],
  rules: [],
  shareDefaults: [],
  accountRoles: defaultAccountRoles(),
  createdRules: [],
  updatedRules: [],
  deletedRuleIds: [],
  enabledChanges: [],
  shareDefaultUpserts: [],
  deletedShareDefaults: [],
  reclassifications: [],
});

let state = fresh();

export function resetFakeApi() {
  state = fresh();
}

/** What the backend received, for assertions. */
export const recorded = {
  approvals: () => state.approvals,
  uploads: () => state.uploads,
  receipts: () => state.receipts,
  createdRules: () => state.createdRules,
  updatedRules: () => state.updatedRules,
  deletedRuleIds: () => state.deletedRuleIds,
  enabledChanges: () => state.enabledChanges,
  shareDefaultUpserts: () => state.shareDefaultUpserts,
  deletedShareDefaults: () => state.deletedShareDefaults,
  reclassifications: () => state.reclassifications,
};

/** Make the next approvals fail the way a ledger rejection does. */
export function rejectApprovals(reason: string) {
  state.ledgerRejection = reason;
}

const ACCOUNTS: LedgerAccount[] = [
  { name: 'Assets:Checking', type: 'Assets' },
  { name: 'Liabilities:CreditCard', type: 'Liabilities' },
  { name: 'Liabilities:SharedAccount', type: 'Liabilities' },
  { name: 'Expenses:Groceries', type: 'Expenses' },
  { name: 'Expenses:Office', type: 'Expenses' },
  { name: 'Expenses:Clothes', type: 'Expenses' },
  { name: 'Expenses:Unallocated', type: 'Expenses' },
  { name: 'Expenses:PurchaseForFlatmate', type: 'Expenses' },
  { name: 'Expenses:FlatmateAdjustment', type: 'Expenses' },
];

function defaultAccountRoles(): AccountRolesResponse {
  return {
    personal_cards: ['Assets:Checking', 'Liabilities:CreditCard'],
    shared_card: 'Liabilities:SharedAccount',
    flatmate_expense_adjustment: 'Expenses:FlatmateAdjustment',
    purchase_for_flatmate: 'Expenses:PurchaseForFlatmate',
    unallocated_account: 'Expenses:Unallocated',
  };
}

/** Seed one classification rule; the normalized pattern is computed like the backend's. */
export function seedRule(
  overrides: Partial<ClassificationRule> & { pattern: string }
): ClassificationRule {
  const { pattern, ...fields } = overrides;
  const rule: ClassificationRule = {
    id: state.nextId++,
    pattern,
    normalized_pattern: normalizeName(pattern),
    max_typos: 1,
    expense_account: 'Expenses:Groceries',
    flatmate_share_override: null,
    enabled: true,
    created_at: '2026-10-01T08:00:00Z',
    ...fields,
  };
  state.rules.push(rule);
  return rule;
}

export function seedShareDefault(expense_account: string, share: number): AccountShareDefault {
  const entry: AccountShareDefault = {
    id: state.nextId++,
    expense_account,
    share,
    created_at: '2026-10-01T08:00:00Z',
  };
  state.shareDefaults.push(entry);
  return entry;
}

type ItemSeed = [
  name: string,
  account: string,
  price: number,
  share?: number,
  matchedRuleId?: number | null,
  overridden?: boolean,
];

export function seedReceipt(
  overrides: Partial<Receipt> & { itemSeeds?: ItemSeed[] } = {}
): Receipt {
  const { itemSeeds, ...fields } = overrides;
  const id = state.nextId++;
  const items = (itemSeeds ?? [['Maito', 'Expenses:Groceries', 2.5]]).map(
    ([
      name,
      expense_account,
      price,
      flatmate_share = 0,
      matched_rule_id = null,
      classification_overridden = false,
    ]) => ({
      id: state.nextId++,
      name,
      expense_account,
      price,
      flatmate_share,
      matched_rule_id,
      classification_overridden,
    })
  );
  const receipt: Receipt = {
    id,
    payee: 'Prisma',
    description: 'Ruokaostokset',
    date: '2026-10-09',
    total_sum: items.reduce((sum, item) => sum + item.price, 0),
    currency: 'EUR',
    status: 'unapproved',
    booked: false,
    source_account: 'Assets:Checking',
    parsed_by: 'anthropic/claude-haiku-4.5',
    items,
    ocr_notes: { suspicious_date: null },
    document: { url: `/api/v1/documents/receipt-${id}.jpg`, mime_type: 'image/jpeg' },
    job_id: null,
    created_at: '2026-10-09T08:00:00Z',
    ...fields,
  };
  state.receipts.unshift(receipt);
  return receipt;
}

export function seedJob(overrides: Partial<Job> = {}): Job {
  const id = state.nextId++;
  const job: Job = {
    id,
    filename: `1760000000000-camera_capture.jpg`,
    mime_type: 'image/jpeg',
    status: 'processed',
    retry_count: 0,
    analysis_error: null,
    document_url: `/api/v1/documents/job-${id}.jpg`,
    created_at: '2026-10-09T08:00:00Z',
    processed_at: '2026-10-09T08:00:05Z',
    ...overrides,
  };
  state.jobs.unshift(job);
  return job;
}

function summary(receipt: Receipt): ReceiptSummary {
  return {
    id: receipt.id,
    payee: receipt.payee,
    description: receipt.description,
    date: receipt.date,
    total_sum: receipt.total_sum,
    currency: receipt.currency,
    status: receipt.status,
    booked: receipt.booked ?? false,
    source_account: receipt.source_account,
    item_count: receipt.items.length,
    has_ocr_issues: Boolean(receipt.ocr_notes?.suspicious_date),
    created_at: receipt.created_at,
  };
}

function page<T>(items: T[], url: URL) {
  const offset = Number(url.searchParams.get('offset') ?? 0);
  const limit = Number(url.searchParams.get('limit') ?? 30);
  return { items: items.slice(offset, offset + limit), total: items.length, offset, limit };
}

function applyRequest(receipt: Receipt, body: ReceiptRequest): Receipt {
  const existing = new Map(receipt.items.map((item) => [item.id, item]));
  return {
    ...receipt,
    payee: body.payee,
    description: body.description ?? null,
    source_account: body.source_account ?? null,
    date: body.date,
    total_sum: body.total_sum,
    currency: body.currency ?? 'EUR',
    items: body.items.map((item) => {
      const before = item.id != null ? existing.get(item.id) : undefined;
      // Editing the account or share is a manual override, like the backend.
      const overridden =
        (before?.classification_overridden ?? false) ||
        (before !== undefined &&
          ((item.expense_account ?? '') !== before.expense_account ||
            (item.flatmate_share ?? 0) !== (before.flatmate_share ?? 0)));
      return {
        id: item.id ?? state.nextId++,
        name: item.name,
        expense_account: item.expense_account ?? before?.expense_account ?? '',
        price: item.price,
        flatmate_share: item.flatmate_share ?? before?.flatmate_share ?? 0,
        matched_rule_id: overridden ? null : (before?.matched_rule_id ?? null),
        classification_overridden: overridden,
      };
    }),
  };
}

/** The fake rule engine: exact normalized match against the enabled rules. */
function reclassify(receipt: Receipt): Receipt {
  const defaults = new Map(
    state.shareDefaults.map((entry) => [entry.expense_account, entry.share])
  );
  const items = receipt.items.map((item) => {
    if (item.classification_overridden) return item;
    const normalized = normalizeName(item.name);
    const rule = state.rules.find(
      (candidate) => candidate.enabled && candidate.normalized_pattern === normalized
    );
    if (!rule) {
      return {
        ...item,
        expense_account: item.expense_account || state.accountRoles.unallocated_account,
        flatmate_share: defaults.get(item.expense_account) ?? 0,
        matched_rule_id: null,
      };
    }
    return {
      ...item,
      expense_account: rule.expense_account,
      flatmate_share: rule.flatmate_share_override ?? defaults.get(rule.expense_account) ?? 0,
      matched_rule_id: rule.id,
    };
  });
  return { ...receipt, items };
}

function replaceReceipt(receipt: Receipt) {
  state.receipts = state.receipts.map((existing) =>
    existing.id === receipt.id ? receipt : existing
  );
}

const notFound = () =>
  HttpResponse.json(
    { error: 'not_found', message: 'The requested resource was not found.' },
    { status: 404 }
  );

// A 1x1 transparent PNG, for <img> requests of stored documents.
const PIXEL = Uint8Array.from(
  atob(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='
  ),
  (char) => char.charCodeAt(0)
);

// Like the backend, a normalized pattern must be unique across rules.
const duplicatePattern = (normalized: string, exceptId: number | null) =>
  state.rules.some((rule) => rule.normalized_pattern === normalized && rule.id !== exceptId);

const conflict = () =>
  HttpResponse.json(
    { error: 'conflict', message: 'A rule with this normalized pattern already exists.' },
    { status: 409 }
  );

export const fakeApiHandlers = [
  http.get('/api/v1/receipts', ({ request }) => {
    const url = new URL(request.url);
    const status = url.searchParams.get('status');
    const matching = state.receipts.filter((receipt) => !status || receipt.status === status);
    return HttpResponse.json(page(matching.map(summary), url));
  }),

  http.get('/api/v1/receipts/:id', ({ params }) => {
    const receipt = state.receipts.find((r) => r.id === Number(params.id));
    return receipt ? HttpResponse.json(receipt) : notFound();
  }),

  http.post('/api/v1/receipts', async ({ request }) => {
    const body = (await request.json()) as ReceiptRequest;
    const receipt = seedReceipt();
    const created = {
      ...applyRequest(receipt, body),
      parsed_by: 'user',
      ocr_notes: null,
      document: null,
    };
    replaceReceipt(created);
    return HttpResponse.json(created, { status: 201 });
  }),

  http.post('/api/v1/receipts/:id/approve', async ({ params, request }) => {
    const receipt = state.receipts.find((r) => r.id === Number(params.id));
    if (!receipt) return notFound();
    const body = (await request.json()) as ReceiptRequest;
    state.approvals.push({ receiptId: receipt.id, body });
    const edited = applyRequest(receipt, body);
    replaceReceipt(edited);
    if (state.ledgerRejection) {
      return HttpResponse.json(
        {
          error: 'bad_gateway',
          message: `The ledger rejected the receipt: ${state.ledgerRejection}`,
        },
        { status: 502 }
      );
    }
    const approved: Receipt = { ...edited, status: 'approved' };
    replaceReceipt(approved);
    return HttpResponse.json(approved);
  }),

  http.delete('/api/v1/receipts/:id', ({ params }) => {
    const before = state.receipts.length;
    state.receipts = state.receipts.filter((r) => r.id !== Number(params.id));
    return state.receipts.length < before ? new HttpResponse(null, { status: 204 }) : notFound();
  }),

  http.post('/api/v1/receipts/:id/reclassify', ({ params }) => {
    const receipt = state.receipts.find((r) => r.id === Number(params.id));
    if (!receipt) return notFound();
    state.reclassifications.push(receipt.id);
    const reclassified = reclassify(receipt);
    replaceReceipt(reclassified);
    return HttpResponse.json(reclassified);
  }),

  http.get('/api/v1/ledger/accounts', ({ request }) => {
    const types = new URL(request.url).searchParams.getAll('type');
    const items = ACCOUNTS.filter((account) => types.length === 0 || types.includes(account.type));
    return HttpResponse.json({ items });
  }),

  http.get('/api/v1/ledger/payees', () =>
    HttpResponse.json({ items: ['Alko', 'K-Market', 'Prisma'] })
  ),

  http.get('/api/v1/ledger/account-roles', () => HttpResponse.json(state.accountRoles)),

  http.get('/api/v1/classification/rules', () => HttpResponse.json({ items: state.rules })),

  http.post('/api/v1/classification/rules', async ({ request }) => {
    const body = (await request.json()) as ClassificationRuleRequest;
    const normalized = normalizeName(body.pattern);
    if (duplicatePattern(normalized, null)) return conflict();
    state.createdRules.push(body);
    const rule: ClassificationRule = {
      id: state.nextId++,
      pattern: body.pattern,
      normalized_pattern: normalized,
      max_typos: body.max_typos ?? 1,
      expense_account: body.expense_account,
      flatmate_share_override: body.flatmate_share_override ?? null,
      enabled: body.enabled ?? true,
      created_at: '2026-10-09T08:00:00Z',
    };
    state.rules.push(rule);
    return HttpResponse.json(rule, { status: 201 });
  }),

  http.put('/api/v1/classification/rules/:id', async ({ params, request }) => {
    const ruleId = Number(params.id);
    const rule = state.rules.find((candidate) => candidate.id === ruleId);
    if (!rule) return notFound();
    const body = (await request.json()) as ClassificationRuleRequest;
    const normalized = normalizeName(body.pattern);
    if (duplicatePattern(normalized, ruleId)) return conflict();
    state.updatedRules.push({ ruleId, body });
    const updated: ClassificationRule = {
      ...rule,
      pattern: body.pattern,
      normalized_pattern: normalized,
      max_typos: body.max_typos ?? rule.max_typos,
      expense_account: body.expense_account,
      flatmate_share_override: body.flatmate_share_override ?? null,
      enabled: body.enabled ?? rule.enabled,
    };
    state.rules = state.rules.map((candidate) => (candidate.id === ruleId ? updated : candidate));
    return HttpResponse.json(updated);
  }),

  http.post('/api/v1/classification/rules/:id/set-enabled', async ({ params, request }) => {
    const ruleId = Number(params.id);
    const rule = state.rules.find((candidate) => candidate.id === ruleId);
    if (!rule) return notFound();
    const body = (await request.json()) as SetRuleEnabledRequest;
    state.enabledChanges.push({ ruleId, enabled: body.enabled });
    const updated: ClassificationRule = { ...rule, enabled: body.enabled };
    state.rules = state.rules.map((candidate) => (candidate.id === ruleId ? updated : candidate));
    return HttpResponse.json(updated);
  }),

  http.delete('/api/v1/classification/rules/:id', ({ params }) => {
    const ruleId = Number(params.id);
    if (!state.rules.some((rule) => rule.id === ruleId)) return notFound();
    state.deletedRuleIds.push(ruleId);
    state.rules = state.rules.filter((rule) => rule.id !== ruleId);
    return new HttpResponse(null, { status: 204 });
  }),

  http.get('/api/v1/classification/account-share-defaults', () =>
    HttpResponse.json({ items: state.shareDefaults })
  ),

  http.put('/api/v1/classification/account-share-defaults', async ({ request }) => {
    const body = (await request.json()) as AccountShareDefaultRequest;
    state.shareDefaultUpserts.push(body);
    const existing = state.shareDefaults.find(
      (entry) => entry.expense_account === body.expense_account
    );
    if (existing) {
      const updated: AccountShareDefault = { ...existing, share: body.share };
      state.shareDefaults = state.shareDefaults.map((entry) =>
        entry.expense_account === body.expense_account ? updated : entry
      );
      return HttpResponse.json(updated);
    }
    const created: AccountShareDefault = {
      id: state.nextId++,
      expense_account: body.expense_account,
      share: body.share,
      created_at: '2026-10-09T08:00:00Z',
    };
    state.shareDefaults.push(created);
    return HttpResponse.json(created);
  }),

  http.delete('/api/v1/classification/account-share-defaults/:expenseAccount', ({ params }) => {
    const expenseAccount = String(params.expenseAccount);
    if (!state.shareDefaults.some((entry) => entry.expense_account === expenseAccount))
      return notFound();
    state.deletedShareDefaults.push(expenseAccount);
    state.shareDefaults = state.shareDefaults.filter(
      (entry) => entry.expense_account !== expenseAccount
    );
    return new HttpResponse(null, { status: 204 });
  }),

  http.get('/api/v1/jobs', ({ request }) =>
    HttpResponse.json(page(state.jobs, new URL(request.url)))
  ),

  http.post('/api/v1/jobs', async ({ request }) => {
    const file = (await request.formData()).get('file');
    if (!(file instanceof File))
      return HttpResponse.json({ detail: [{ msg: 'Field required' }] }, { status: 422 });
    state.uploads.push({ name: file.name, type: file.type, size: file.size });
    const job = seedJob({ status: 'waiting', mime_type: file.type, processed_at: null });
    return HttpResponse.json(job, { status: 201 });
  }),

  http.post('/api/v1/jobs/:id/retry', ({ params }) => {
    const job = state.jobs.find((j) => j.id === Number(params.id));
    if (!job) return notFound();
    const retried: Job = { ...job, status: 'waiting', retry_count: 0, analysis_error: null };
    state.jobs = state.jobs.map((j) => (j.id === job.id ? retried : j));
    return HttpResponse.json(retried);
  }),

  http.get('/api/v1/documents/:name', () =>
    HttpResponse.arrayBuffer(PIXEL.buffer, { headers: { 'Content-Type': 'image/png' } })
  ),
];
