import { Combobox } from '@/components/common/Combobox';
import { NumberInput } from '@/components/common/NumberInput';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

/** The editable fields of a classification rule, as form state. */
export interface RuleFormValue {
  pattern: string;
  account: string;
  /** The share override as text; blank means the account's default share. */
  share: string;
  maxTypos: number;
  enabled: boolean;
}

/** A rule being edited in a dialog; `id` is null for a new rule. */
export type EditableRule = RuleFormValue & { id: number | null };

/**
 * The rule form fields shared by the rules screen's edit dialog and the
 * review screen's save-as-rule dialog: pattern, expense account (a combobox
 * of the ledger's expense accounts, never free text), optional share
 * override and max typos.
 */
export function RuleFormFields({
  value,
  onChange,
  expenseAccounts,
  accountDefaultShare,
  showEnabled = true,
}: {
  value: RuleFormValue;
  onChange: (patch: Partial<RuleFormValue>) => void;
  expenseAccounts: readonly string[];
  accountDefaultShare: number | undefined;
  showEnabled?: boolean;
}) {
  return (
    <div className="grid gap-3">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="rule-pattern">Pattern (normalized product name)</Label>
        <Input
          id="rule-pattern"
          value={value.pattern}
          onChange={(event) => onChange({ pattern: event.target.value })}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label>Expense account</Label>
        <Combobox
          label="Rule expense account"
          value={value.account}
          onChange={(account) => onChange({ account })}
          options={expenseAccounts}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rule-share">Flatmate share override (blank = account default)</Label>
          <NumberInput
            id="rule-share"
            min={0}
            max={100}
            step={1}
            placeholder={
              accountDefaultShare !== undefined
                ? `default: ${accountDefaultShare}%`
                : 'default: none'
            }
            value={value.share}
            onChange={(event) => onChange({ share: event.target.value })}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rule-typos">Max typos</Label>
          <NumberInput
            id="rule-typos"
            min={0}
            max={2}
            step={1}
            value={value.maxTypos}
            onChange={(event) => {
              const parsed = event.target.valueAsNumber;
              onChange({ maxTypos: Number.isNaN(parsed) ? 0 : parsed });
            }}
          />
        </div>
      </div>
      {showEnabled && (
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={value.enabled}
            onCheckedChange={(checked) => onChange({ enabled: checked === true })}
            aria-label="Rule enabled"
          />
          Enabled
        </label>
      )}
    </div>
  );
}
