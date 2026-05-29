import type { BasicFormState, YesNoUnknown } from "@/types/itr";

type IntakeFormProps = {
  form: BasicFormState;
  missingFields: string[];
  disabled: boolean;
  onChange: (field: keyof BasicFormState, value: string) => void;
  onSubmit: () => void;
};

const inputClass =
  "mt-2 w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-[#111827] outline-none transition focus:border-[#22c55e] focus:ring-2 focus:ring-[#22c55e]/20 disabled:bg-gray-100";

const labelClass = "text-sm font-medium text-gray-700";

export function IntakeForm({ form, missingFields, disabled, onChange, onSubmit }: IntakeFormProps) {
  const showPreviousYear = missingFields.includes("previous_year") || form.previousYear;
  const showReturnReason =
    missingFields.includes("return_filing_reason.type") || form.returnFilingReason !== "unknown";
  const showDefective =
    missingFields.includes("is_defective_return_case") || form.isDefectiveReturnCase !== "unknown";
  const showForeign = true;
  const showPresumptive = true;

  return (
    <section className="rounded-2xl border border-[#e5e7eb] bg-white p-6 shadow-sm">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#22c55e]">
            Guided intake
          </p>
          <h2 className="mt-1 text-2xl font-semibold text-[#111827]">Taxpayer profile</h2>
          <p className="mt-2 text-sm leading-6 text-gray-600">
            Start with the minimum profile. The agent will reveal only the fields needed by the
            deterministic rules.
          </p>
        </div>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <TextInput label="PAN" value={form.pan} disabled={disabled} onChange={(value) => onChange("pan", value)} />
        <TextInput
          label="Aadhaar"
          value={form.aadhaar}
          disabled={disabled}
          onChange={(value) => onChange("aadhaar", value)}
        />
        <SelectInput
          label="Entity Type"
          value={form.entityType}
          disabled={disabled}
          onChange={(value) => onChange("entityType", value)}
          options={[
            ["individual", "Individual"],
            ["huf", "HUF"],
            ["firm", "Firm"],
            ["llp", "LLP"],
            ["company", "Company"],
            ["trust", "Trust"],
          ]}
        />
        <SelectInput
          label="Residency"
          value={form.residency}
          disabled={disabled}
          onChange={(value) => onChange("residency", value)}
          options={[
            ["resident", "Resident"],
            ["rnor", "RNOR"],
            ["non_resident", "Non-resident"],
            ["unknown", "Unknown"],
          ]}
        />
        <TextInput
          label="Salary Income"
          value={form.salaryIncome}
          disabled={disabled}
          inputMode="numeric"
          onChange={(value) => onChange("salaryIncome", value)}
        />
        <TextInput
          label="Business / Profession Income"
          value={form.businessProfessionIncome}
          disabled={disabled}
          inputMode="numeric"
          helpText="Use 0 if this does not apply."
          onChange={(value) => onChange("businessProfessionIncome", value)}
        />
        <TextInput
          label="Capital Gains Income"
          value={form.capitalGainsIncome}
          disabled={disabled}
          inputMode="numeric"
          helpText="Total capital gains. Use the fields below to classify the type."
          onChange={(value) => onChange("capitalGainsIncome", value)}
        />
        <YesNoInput
          label="Short-term Capital Gains"
          value={form.hasStcg}
          disabled={disabled}
          onChange={(value) => onChange("hasStcg", value)}
        />
        <YesNoInput
          label="LTCG under Section 112A"
          value={form.hasLtcg112A}
          disabled={disabled}
          onChange={(value) => onChange("hasLtcg112A", value)}
        />
        <TextInput
          label="LTCG 112A Amount"
          value={form.ltcg112AAmount}
          disabled={disabled}
          inputMode="numeric"
          helpText="Use 0 if section 112A does not apply."
          onChange={(value) => onChange("ltcg112AAmount", value)}
        />
        <YesNoInput
          label="Other LTCG"
          value={form.hasOtherLtcg}
          disabled={disabled}
          onChange={(value) => onChange("hasOtherLtcg", value)}
        />
        <YesNoInput
          label="Land / Building Capital Gains"
          value={form.hasLandBuildingGains}
          disabled={disabled}
          onChange={(value) => onChange("hasLandBuildingGains", value)}
        />
        <YesNoInput
          label="Special-rate Capital Gains"
          value={form.hasSpecialRateCapitalGains}
          disabled={disabled}
          onChange={(value) => onChange("hasSpecialRateCapitalGains", value)}
        />
        <TextInput
          label="Bank Interest / Other Sources"
          value={form.otherSourcesIncome}
          disabled={disabled}
          inputMode="numeric"
          helpText="Use this for bank interest and similar income."
          onChange={(value) => onChange("otherSourcesIncome", value)}
        />
        <TextInput
          label="Agricultural Income"
          value={form.agriculturalIncome}
          disabled={disabled}
          inputMode="numeric"
          helpText="Kept separate from bank interest for ITR-1/ITR-4 checks."
          onChange={(value) => onChange("agriculturalIncome", value)}
        />

        {showPreviousYear ? (
          <TextInput
            animated
            label="Previous Year"
            value={form.previousYear}
            disabled={disabled}
            onChange={(value) => onChange("previousYear", value)}
          />
        ) : null}

        {showReturnReason ? (
          <SelectInput
            animated
            label="Return Filing Reason"
            value={form.returnFilingReason}
            disabled={disabled}
            onChange={(value) => onChange("returnFilingReason", value)}
            options={[
              ["voluntary", "Voluntary"],
              ["mandatory", "Mandatory"],
              ["notice", "Notice"],
              ["unknown", "Unknown"],
            ]}
          />
        ) : null}

        {showDefective ? (
          <YesNoInput
            animated
            label="Defective Return Case"
            value={form.isDefectiveReturnCase}
            disabled={disabled}
            onChange={(value) => onChange("isDefectiveReturnCase", value)}
          />
        ) : null}

        {showForeign ? (
          <>
            <YesNoInput
              animated
              label="Foreign Assets"
              value={form.hasForeignAssets}
              disabled={disabled}
              onChange={(value) => onChange("hasForeignAssets", value)}
            />
            <YesNoInput
              animated
              label="Foreign Income"
              value={form.hasForeignIncome}
              disabled={disabled}
              onChange={(value) => onChange("hasForeignIncome", value)}
            />
          </>
        ) : null}

        {showPresumptive ? (
          <YesNoInput
            animated
            label="Presumptive Taxation"
            value={form.presumptiveTaxation}
            disabled={disabled}
            onChange={(value) => onChange("presumptiveTaxation", value)}
          />
        ) : null}
        <YesNoInput
          label="Director in Company"
          value={form.directorInCompany}
          disabled={disabled}
          onChange={(value) => onChange("directorInCompany", value)}
        />
        <YesNoInput
          label="Unlisted Equity Held"
          value={form.unlistedEquityHeld}
          disabled={disabled}
          onChange={(value) => onChange("unlistedEquityHeld", value)}
        />
        <YesNoInput
          label="Brought Forward Losses"
          value={form.broughtForwardLosses}
          disabled={disabled}
          onChange={(value) => onChange("broughtForwardLosses", value)}
        />
        <YesNoInput
          label="RSU / Capital Gains Classification Unclear"
          value={form.capitalGainsEdgeCase}
          disabled={disabled}
          onChange={(value) => onChange("capitalGainsEdgeCase", value)}
        />
        <YesNoInput
          label="Section 80C"
          value={form.has80C}
          disabled={disabled}
          onChange={(value) => onChange("has80C", value)}
        />
        <YesNoInput
          label="Section 80D"
          value={form.has80D}
          disabled={disabled}
          onChange={(value) => onChange("has80D", value)}
        />
      </div>

      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          disabled={disabled}
          onClick={onSubmit}
          className="cursor-pointer rounded-lg bg-[#22c55e] px-5 py-3 text-sm font-semibold text-white transition hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-[#22c55e]/30 disabled:cursor-not-allowed disabled:opacity-70"
        >
          Run agent workflow
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() => window.location.reload()}
          className="cursor-pointer rounded-lg border border-gray-300 px-5 py-3 text-sm font-semibold text-gray-700 transition hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-300 disabled:cursor-not-allowed disabled:opacity-70"
        >
          Reset
        </button>
      </div>
    </section>
  );
}

function TextInput({
  label,
  value,
  disabled,
  animated,
  inputMode,
  helpText,
  onChange,
}: {
  label: string;
  value: string;
  disabled: boolean;
  animated?: boolean;
  inputMode?: "numeric";
  helpText?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className={animated ? "fade-in block" : "block"}>
      <span className={labelClass}>{label}</span>
      <input
        className={inputClass}
        value={value}
        disabled={disabled}
        inputMode={inputMode}
        onChange={(event) => onChange(event.target.value)}
      />
      {helpText ? <span className="mt-1 block text-xs text-gray-500">{helpText}</span> : null}
    </label>
  );
}

function SelectInput({
  label,
  value,
  disabled,
  animated,
  options,
  onChange,
}: {
  label: string;
  value: string;
  disabled: boolean;
  animated?: boolean;
  options: [string, string][];
  onChange: (value: string) => void;
}) {
  return (
    <label className={animated ? "fade-in block" : "block"}>
      <span className={labelClass}>{label}</span>
      <select
        className={inputClass}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>
            {optionLabel}
          </option>
        ))}
      </select>
    </label>
  );
}

function YesNoInput({
  label,
  value,
  disabled,
  animated,
  onChange,
}: {
  label: string;
  value: YesNoUnknown;
  disabled: boolean;
  animated?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <SelectInput
      animated={animated}
      label={label}
      value={value}
      disabled={disabled}
      onChange={onChange}
      options={[
        ["yes", "Yes"],
        ["no", "No"],
        ["unknown", "Unknown"],
      ]}
    />
  );
}
