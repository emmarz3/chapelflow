import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus, Trash2, UserRoundCheck } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import {
  Badge,
  Button,
  ErrorState,
  LoadingState,
  Modal,
  PageHeader,
  useToast,
} from "../components/ui";
import {
  adminAccountService,
  chapelGroupService,
  institutionalAccountService,
} from "../services/chapelflow";
import { ApiError } from "../lib/api";

const roles = [
  ["CHAPLAIN", "Chaplain"],
  ["STUDENT_CHAPLAIN", "Student Chaplain"],
  ["ASSISTANT_STUDENT_CHAPLAIN", "Assistant Student Chaplain"],
  ["HOSTEL_COORDINATOR", "Hostel Fellowship Coordinator"],
  ["UNIT_HEAD", "Unit leader"],
  ["FELLOWSHIP_LEADER", "Fellowship leader"],
  ["ATTENDANCE_USHER", "Attendance usher"],
] as const;

type InstitutionalRole = (typeof roles)[number][0];

// Official office titles are distinct from permissions and Chapel group identities.
// No incumbent names are stored in this catalog.
const offices: ReadonlyArray<{
  code: string;
  label: string;
  role: InstitutionalRole;
  unit?: string;
}> = [
  { code: "CHAPLAIN", label: "Chaplain", role: "CHAPLAIN" },
  { code: "STUDENT_CHAPLAIN", label: "Student Chaplain", role: "STUDENT_CHAPLAIN" },
  { code: "ASSISTANT_STUDENT_CHAPLAIN_VLBC_ANNEX", label: "Assistant Student Chaplain VLBC Annex Hostel", role: "ASSISTANT_STUDENT_CHAPLAIN" },
  { code: "UNIT_HEAD", label: "Unit leader (select unit)", role: "UNIT_HEAD" },
  { code: "INTERCESSORY", label: "Intercessory", role: "UNIT_HEAD", unit: "Intercessory" },
  { code: "TREASURER", label: "Treasurer", role: "UNIT_HEAD", unit: "Treasurer" },
  { code: "CHAPEL_PROTOCOL", label: "Chapel Protocol", role: "UNIT_HEAD", unit: "Chapel Protocol" },
  { code: "HEAD_OF_MUSIC", label: "Head of Music", role: "UNIT_HEAD", unit: "Music" },
  { code: "ASSISTANT_HEAD_OF_MUSIC", label: "Assistant Head of Music", role: "UNIT_HEAD", unit: "Music" },
  { code: "HEAD_OF_INSTRUMENTALIST", label: "Head of Instrumentalist", role: "UNIT_HEAD", unit: "Instrumentalist" },
  { code: "CHIEF_USHER", label: "Chief Usher", role: "UNIT_HEAD", unit: "Ushering" },
  { code: "ASSISTANT_CHIEF_USHER", label: "Assistant Chief Usher", role: "UNIT_HEAD", unit: "Ushering" },
  { code: "HEAD_OF_SANCTUARY_KEEPERS", label: "Head of Sanctuary Keepers", role: "UNIT_HEAD", unit: "Sanctuary Keepers" },
  { code: "ASSISTANT_HEAD_OF_SANCTUARY_KEEPERS", label: "Assistant Head of Sanctuary Keepers", role: "UNIT_HEAD", unit: "Sanctuary Keepers" },
  { code: "MEDIA_ICT", label: "Media & ICT", role: "UNIT_HEAD", unit: "Media & ICT" },
  { code: "SOCIAL_MEDIA", label: "Social Media", role: "UNIT_HEAD", unit: "Social Media" },
  { code: "LIBRARY", label: "Library", role: "UNIT_HEAD", unit: "Library" },
  { code: "DRAMA_TEAM", label: "Drama Team", role: "UNIT_HEAD", unit: "Drama Team" },
  { code: "TECHNICAL_SOUND", label: "Technical & Sound", role: "UNIT_HEAD", unit: "Technical & Sound" },
  { code: "FELLOWSHIP_LEADER", label: "Campus Fellowship Leader (select fellowship)", role: "FELLOWSHIP_LEADER" },
  { code: "MALE_HOSTEL_FELLOWSHIP_COORDINATOR", label: "Male Hostel Fellowship Coordinator", role: "HOSTEL_COORDINATOR" },
  { code: "FEMALE_HOSTEL_FELLOWSHIP_COORDINATOR_1", label: "Female Hostel Fellowship Coordinator 1", role: "HOSTEL_COORDINATOR" },
  { code: "FEMALE_HOSTEL_FELLOWSHIP_COORDINATOR_2", label: "Female Hostel Fellowship Coordinator 2", role: "HOSTEL_COORDINATOR" },
  { code: "ATTENDANCE_USHER", label: "Attendance usher", role: "ATTENDANCE_USHER" },
];

function roleGroupType(role: InstitutionalRole) {
  if (role === "UNIT_HEAD") return "UNIT";
  if (role === "FELLOWSHIP_LEADER") return "FELLOWSHIP";
  return null;
}

function validationMessage(error: unknown, field: string) {
  return error instanceof ApiError ? error.fieldErrors?.[field]?.join(" ") : undefined;
}

export function InstitutionalAccountsPage() {
  const client = useQueryClient();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [preparingGroup, setPreparingGroup] = useState(false);
  const [selectedRole, setSelectedRole] = useState<InstitutionalRole>("CHAPLAIN");
  const [selectedGroup, setSelectedGroup] = useState("");
  const [selectedOffice, setSelectedOffice] = useState("CHAPLAIN");
  const [resetAccount, setResetAccount] = useState<{ id: string; name: string; scope: "institutional" | "all" } | null>(null);
  const [deleteAccount, setDeleteAccount] = useState<{ id: string; name: string } | null>(null);
  const [eraseAccount, setEraseAccount] = useState<{ id: string; name: string; identifier: string } | null>(null);
  const [temporaryPassword, setTemporaryPassword] = useState("");
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const accounts = useQuery({
    queryKey: ["institutional-accounts"],
    queryFn: async () => (await institutionalAccountService.list()).data,
  });
  const groups = useQuery({
    queryKey: ["chapel-groups", "institutional-accounts"],
    queryFn: async () => (await chapelGroupService.list({ accountAssignment: true })).data,
  });
  const directory = useQuery({
    queryKey: ["admin-account-directory", page, search],
    queryFn: async () => (await adminAccountService.list(page, search)).data,
  });
  const selectedOfficeDetails = offices.find((office) => office.code === selectedOffice);
  const fixedUnit = selectedOfficeDetails?.unit;
  const groupType = roleGroupType(selectedRole);
  const resolvedGroup = fixedUnit
    ? (groups.data?.find((group) =>
        group.name === fixedUnit && group.group_type === "UNIT" && group.is_active,
      )?.id ?? "")
    : selectedGroup;
  const refresh = () =>
    void Promise.all([
      client.invalidateQueries({ queryKey: ["institutional-accounts"] }),
      client.invalidateQueries({ queryKey: ["admin-account-directory"] }),
    ]);
  const create = useMutation({
    mutationFn: institutionalAccountService.create,
    onSuccess: () => {
      setOpen(false);
      toast("Institutional account created successfully.");
      refresh();
    },
  });
  const addUnits = useMutation({
    mutationFn: chapelGroupService.bootstrapChapelGroups,
    onSuccess: (response) => {
      toast(`${response.data.count} chapel group${response.data.count === 1 ? "" : "s"} added.`);
      void client.invalidateQueries({ queryKey: ["chapel-groups"] });
    },
  });
  const update = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      institutionalAccountService.update(id, { is_active }),
    onSuccess: refresh,
  });
  const reset = useMutation({
    mutationFn: ({ id, scope }: { id: string; scope: "institutional" | "all" }) =>
      scope === "all" ? adminAccountService.resetPassword(id) : institutionalAccountService.resetPassword(id),
    onSuccess: (response) => {
      setTemporaryPassword(response.data.temporary_password);
      refresh();
    },
  });
  const remove = useMutation({
    mutationFn: institutionalAccountService.remove,
    onSuccess: () => {
      setDeleteAccount(null);
      toast("Institutional account removed and access revoked.");
      refresh();
    },
  });
  const erase = useMutation({
    mutationFn: ({ id, confirmation, password, otp }: { id: string; confirmation: string; password: string; otp: string }) =>
      adminAccountService.erase(id, confirmation, password, otp),
    onSuccess: () => {
      setEraseAccount(null);
      toast("Account and linked member profile deleted.");
      refresh();
    },
  });
  const resetPreview = useMutation({ mutationFn: adminAccountService.resetPreview });
  const freshStart = useMutation({
    mutationFn: ({ token, confirmation, password, otp }: { token: string; confirmation: string; password: string; otp: string }) =>
      adminAccountService.resetDatabase(token, confirmation, password, otp),
    onSuccess: () => window.location.assign("/login"),
  });
  function closeReset() {
    if (reset.isPending) return;
    setResetAccount(null);
    setTemporaryPassword("");
    reset.reset();
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const role = String(data.get("role")) as InstitutionalRole;
    const requestedGroupType = roleGroupType(role);
    const office = role === "FELLOWSHIP_LEADER"
      ? "FELLOWSHIP_LEADER"
      : String(data.get("institutional_office") || selectedOffice);
    let groupId = resolvedGroup;
    if (requestedGroupType && !groupId) {
      setPreparingGroup(true);
      try {
        await chapelGroupService.bootstrapChapelGroups();
        const availableGroups = (await chapelGroupService.list({ accountAssignment: true })).data;
        groupId = availableGroups.find((group) =>
          group.is_active &&
          group.group_type === requestedGroupType &&
          (fixedUnit ? group.name === fixedUnit : group.id === selectedGroup),
        )?.id ?? "";
        void client.invalidateQueries({ queryKey: ["chapel-groups"] });
      } catch (error) {
        toast(error instanceof Error ? error.message : "Could not prepare the required Chapel group.", "error");
        return;
      } finally {
        setPreparingGroup(false);
      }
      if (!groupId) {
        toast("The required active Chapel Unit or Fellowship could not be found. Check the Chapel group catalog and try again.", "error");
        return;
      }
    }
    create.mutate({
      first_name: String(data.get("first_name")),
      last_name: String(data.get("last_name")),
      email: String(data.get("email")),
      password: String(data.get("password")),
      role,
      institutional_office: office,
      password_change_required: true,
      ...(requestedGroupType ? { institutional_group: groupId } : {}),
    });
  }
  useEffect(() => {
    if (!accounts.isPending && window.location.hash === "#launch-reset") {
      document.getElementById("launch-reset")?.scrollIntoView({ block: "start" });
    }
  }, [accounts.isPending]);

  if (accounts.isPending)
    return <LoadingState label="Loading institutional accounts" />;
  if (accounts.isError)
    return (
      <ErrorState
        description={accounts.error.message}
        onRetry={() => void accounts.refetch()}
      />
    );
  return (
    <div className="motion-feature">
      <PageHeader
        eyebrow="Super administration"
        title="Institutional accounts"
        description="Create accounts for every Chapel leadership office, including assistant heads and hostel fellowship coordinators. No names are preloaded."
        actions={
          <div className="button-row">
            <Button variant="secondary" loading={addUnits.isPending} onClick={() => addUnits.mutate()}>
              Add chapel units & fellowships
            </Button>
            <Button icon={<Plus />} onClick={() => setOpen((value) => !value)}>
              Create account
            </Button>
          </div>
        }
      />
      {addUnits.isError && <p className="form-error" role="alert">{addUnits.error.message}</p>}
      {open && (
        <form
          className="panel form-grid"
          onInput={() => {
            if (create.isError) create.reset();
          }}
          onSubmit={submit}
        >
          <label className="field">
            <span>First name</span>
            <input name="first_name" required />
          </label>
          <label className="field">
            <span>Last name</span>
            <input name="last_name" required />
          </label>
          <label className="field">
            <span>Email</span>
            <input
              name="email"
              type="email"
              required
              aria-invalid={Boolean(validationMessage(create.error, "email"))}
              aria-describedby="institutional-email-note institutional-email-error"
            />
            <small id="institutional-email-note">
              Use a unique email address; it cannot be the Super Admin email.
            </small>
            {validationMessage(create.error, "email") && (
              <small id="institutional-email-error" className="field__error" role="alert">
                {validationMessage(create.error, "email")}
              </small>
            )}
          </label>
          <label className="field">
            <span>Initial password</span>
            <input
              name="password"
              type="password"
              minLength={8}
              required
              aria-invalid={Boolean(validationMessage(create.error, "password"))}
              aria-describedby="institutional-password-note institutional-password-error"
            />
            <small id="institutional-password-note">Use at least 8 characters and avoid common passwords.</small>
            {validationMessage(create.error, "password") && (
              <small id="institutional-password-error" className="field__error" role="alert">
                {validationMessage(create.error, "password")}
              </small>
            )}
          </label>
          <label className="field">
            <span>Role</span>
            <select
              name="role"
              value={selectedRole}
              onChange={(event) => {
                const nextRole = event.target.value as InstitutionalRole;
                setSelectedRole(nextRole);
                setSelectedOffice(offices.find((office) => office.role === nextRole)?.code ?? "");
                setSelectedGroup("");
              }}
              aria-invalid={Boolean(validationMessage(create.error, "role"))}
              aria-describedby="institutional-role-error"
            >
              {roles.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            {validationMessage(create.error, "role") && (
              <small id="institutional-role-error" className="field__error" role="alert">
                {validationMessage(create.error, "role")}
              </small>
            )}
          </label>
          {selectedRole !== "FELLOWSHIP_LEADER" && <label className="field">
            <span>Leadership office</span>
            <select
              name="institutional_office"
              aria-label="Leadership office"
              value={selectedOffice}
              required
              onChange={(event) => {
                setSelectedOffice(event.target.value);
                setSelectedGroup("");
              }}
              aria-invalid={Boolean(validationMessage(create.error, "institutional_office"))}
            >
              {offices
                .filter((office) => office.role === selectedRole)
                .map((office) => (
                  <option key={office.code} value={office.code}>{office.label}</option>
                ))}
            </select>
            {validationMessage(create.error, "institutional_office") && (
              <small className="field__error" role="alert">
                {validationMessage(create.error, "institutional_office")}
              </small>
            )}
            <small>Choose the exact leadership position from the Chapel register.</small>
          </label>}
          {groupType && <label className="field">
            <span>Unit or fellowship</span>
            <select
              name="institutional_group"
              value={resolvedGroup}
              disabled={groups.isPending || !groupType || Boolean(fixedUnit)}
              required={Boolean(groupType)}
              onChange={(event) => setSelectedGroup(event.target.value)}
              aria-invalid={Boolean(validationMessage(create.error, "institutional_group"))}
              aria-describedby="institutional-group-note institutional-group-error"
            >
              <option value="">
                {groupType ? (fixedUnit ? `Assigned to ${fixedUnit}` : "Select an assignment") : "Not applicable to this role"}
              </option>
              {groups.data
                ?.filter(
                  (group) =>
                    group.is_active &&
                    group.group_type === groupType &&
                    (!fixedUnit || group.name === fixedUnit),
                )
                .map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name} · {group.group_type.toLowerCase()}
                  </option>
                ))}
            </select>
            <small id="institutional-group-note">
              {fixedUnit
                ? "This office is tied to the named Chapel Unit. Add the standard groups first if it is missing."
                : groupType
                  ? "Leaders are assigned only to their matching unit or fellowship."
                  : "This leadership office does not require a Unit or Fellowship assignment."}
            </small>
            {validationMessage(create.error, "institutional_group") && (
              <small id="institutional-group-error" className="field__error" role="alert">
                {validationMessage(create.error, "institutional_group")}
              </small>
            )}
          </label>}
          <div>
            <Button type="submit" loading={create.isPending || preparingGroup}>
              Create securely
            </Button>
            {create.isError && (
              <p className="form-error" role="alert">
                {create.error.message}
              </p>
            )}
          </div>
        </form>
      )}
      <section className="table-panel">
        <header>
          <div className="panel-heading">
            <div>
              <h2>Chapel accounts</h2>
              <p>
                Only Super Admins can make changes. Existing passwords are
                never visible; temporary passwords appear once after a reset.
              </p>
            </div>
          </div>
        </header>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Role</th>
              <th>Office & assignment</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {accounts.data.map((account) => (
              <tr key={account.id}>
                <td>
                  <strong>
                    {account.first_name} {account.last_name}
                  </strong>
                  <small>{account.email}</small>
                </td>
                <td>
                  {roles.find(([role]) => role === account.role)?.[1] ||
                    account.role}
                </td>
                <td>
                  <strong>{offices.find((office) => office.code === account.institutional_office)?.label || "Not specified"}</strong>
                  {account.institutional_group && (
                    <small>{groups.data?.find((group) => group.id === account.institutional_group)?.name || "Assigned Chapel group"}</small>
                  )}
                </td>
                <td>
                  <Badge tone={account.is_active ? "success" : "danger"}>
                    {account.is_active ? "Active" : "Suspended"}
                  </Badge>
                  {account.password_change_required && (
                    <Badge tone="warning">Password change required</Badge>
                  )}
                </td>
                <td className="button-row">
                  <Button
                    variant="secondary"
                    icon={<UserRoundCheck />}
                    onClick={() =>
                      update.mutate({
                        id: account.id,
                        is_active: !account.is_active,
                      })
                    }
                  >
                    {account.is_active ? "Suspend" : "Activate"}
                  </Button>
                  <Button
                    variant="ghost"
                    icon={<KeyRound />}
                    onClick={() =>
                      setResetAccount({
                        id: account.id,
                        name: `${account.first_name} ${account.last_name}`,
                        scope: "institutional",
                      })
                    }
                  >
                    Reset password
                  </Button>
                  <Button variant="ghost" icon={<Trash2 />} onClick={() => setDeleteAccount({
                    id: account.id,
                    name: `${account.first_name} ${account.last_name}`,
                  })}>Delete account</Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="table-panel">
        <header>
          <div className="panel-heading"><div><h2>All accounts</h2><p>View every account. Passwords cannot be viewed; issue a one-time temporary password when access needs to be restored.</p></div></div>
          <form className="button-row" onSubmit={(event) => { event.preventDefault(); setPage(1); setSearch(searchDraft.trim()); }}>
            <input aria-label="Search all accounts" value={searchDraft} onChange={(event) => setSearchDraft(event.target.value)} placeholder="Name, email, or matric number" />
            <Button type="submit" variant="secondary">Search</Button>
          </form>
        </header>
        {directory.isPending ? <LoadingState label="Loading all accounts" /> : directory.isError ?
          <ErrorState description={directory.error.message} onRetry={() => void directory.refetch()} /> : <>
            <table>
              <thead><tr><th>Account</th><th>Role</th><th>Branch</th><th>Status</th><th>Action</th></tr></thead>
              <tbody>{directory.data.items.map((account) => <tr key={account.id}>
                <td><strong>{account.name || account.email || account.matric_no || "Unnamed account"}</strong><small>{account.email || account.matric_no}</small></td>
                <td>{account.role || "Member"}</td>
                <td>{account.branch_name || "Global"}</td>
                <td><Badge tone={account.deleted_at || !account.is_active ? "danger" : "success"}>{account.deleted_at ? "Removed" : account.is_active ? "Active" : "Suspended"}</Badge></td>
                <td className="button-row">
                  {account.can_reset && <Button variant="ghost" icon={<KeyRound />} onClick={() => setResetAccount({ id: account.id, name: account.name || account.email || account.matric_no, scope: "all" })}>Reset password</Button>}
                  {account.role !== "SUPER_ADMIN" && <Button variant="ghost" icon={<Trash2 />} onClick={() => setEraseAccount({ id: account.id, name: account.name || account.email || account.matric_no, identifier: account.email || account.matric_no })}>Delete account and member data</Button>}
                </td>
              </tr>)}</tbody>
            </table>
            {directory.data.items.length === 0 && <p>No matching accounts.</p>}
            <div className="button-row">
              <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>Previous</Button>
              <span>Page {page} · {directory.data.count} accounts</span>
              <Button variant="secondary" disabled={page * directory.data.page_size >= directory.data.count} onClick={() => setPage((current) => current + 1)}>Next</Button>
            </div>
          </>}
      </section>
      <section className="panel">
        <h2 id="launch-reset" style={{ scrollMarginTop: 100 }}>Fresh launch: reset saved data</h2>
        <p>Deletes all other accounts and saved application records, including member profiles, attendance, finance, messages, gallery and website content, upload references, and previous audit history. Your Super Admin sign-in and authenticator remain. Chapel branches, academic programmes, units, fellowships, and role permissions are preserved. The application code, database structure, hosting settings, and integrations stay intact. Files stored in Cloudinary or S3 and external payment records are not deleted.</p>
        <p>Make and verify a database backup before using this. The reset cannot be undone from this dashboard.</p>
        <Button variant="secondary" loading={resetPreview.isPending} onClick={() => resetPreview.mutate()}>Review launch reset</Button>
        {resetPreview.isError && <p className="form-error" role="alert">{resetPreview.error.message}</p>}
      </section>
      <Modal open={Boolean(eraseAccount)} onClose={() => { if (!erase.isPending) { setEraseAccount(null); erase.reset(); } }}
        title="Delete account and member data" description={`Delete ${eraseAccount?.name || "this account"}? Their linked member profile and Upper Room posts will be removed. Financial, audit and shared public records remain.`}>
        <form className="form-grid" onSubmit={(event) => {
          event.preventDefault();
          if (!eraseAccount) return;
          const data = new FormData(event.currentTarget);
          erase.mutate({ id: eraseAccount.id, confirmation: String(data.get("confirmation")), password: String(data.get("password")), otp: String(data.get("otp")) });
        }}>
          <label className="field"><span>Type {eraseAccount?.identifier} to confirm</span><input name="confirmation" required autoComplete="off" /></label>
          <label className="field"><span>Your Super Admin password</span><input name="password" type="password" required autoComplete="current-password" /></label>
          <label className="field"><span>Authenticator code</span><input name="otp" inputMode="numeric" pattern="[0-9]{6}" required autoComplete="one-time-code" /></label>
          {erase.isError && <p className="form-error" role="alert">{erase.error.message}</p>}
          <div className="button-row"><Button type="button" variant="ghost" onClick={() => setEraseAccount(null)}>Cancel</Button><Button type="submit" loading={erase.isPending}>Delete this account</Button></div>
        </form>
      </Modal>
      <Modal open={Boolean(resetPreview.data)} onClose={() => { if (!freshStart.isPending) { resetPreview.reset(); freshStart.reset(); } }}
        title="Reset saved data for launch" description="Review the counts and confirm the permanent fresh start.">
        {resetPreview.data && <form className="form-grid" onSubmit={(event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          freshStart.mutate({ token: resetPreview.data.data.token, confirmation: String(data.get("confirmation")), password: String(data.get("password")), otp: String(data.get("otp")) });
        }}>
          <p>{resetPreview.data.data.database_rows} database rows reviewed. This reset removes {resetPreview.data.data.accounts_to_remove} other accounts and all operational records, while preserving system configuration and your Super Admin access. The preview expires after five minutes or if records change.</p>
          <p>Uploaded files and external service data remain. Confirm your backup can be restored before proceeding.</p>
          <label className="field"><span>Type {resetPreview.data.data.confirmation}</span><input name="confirmation" required autoComplete="off" /></label>
          <label className="field"><span>Your Super Admin password</span><input name="password" type="password" required autoComplete="current-password" /></label>
          <label className="field"><span>Authenticator code</span><input name="otp" inputMode="numeric" pattern="[0-9]{6}" required autoComplete="one-time-code" /></label>
          <label><input type="checkbox" name="backup" required /> I have verified a restorable database backup.</label>
          {freshStart.isError && <p className="form-error" role="alert">{freshStart.error.message}</p>}
          <div className="button-row"><Button type="button" variant="ghost" onClick={() => resetPreview.reset()}>Cancel</Button><Button type="submit" loading={freshStart.isPending}>Reset saved accounts and records</Button></div>
        </form>}
      </Modal>
      <Modal open={Boolean(deleteAccount)} onClose={() => { if (!remove.isPending) { setDeleteAccount(null); remove.reset(); } }} title="Delete institutional account" description={`Remove ${deleteAccount?.name || "this account"} from institutional accounts? Their sign-in access will be revoked. Historical records will remain.`} footer={<>
        <Button variant="ghost" onClick={() => setDeleteAccount(null)} disabled={remove.isPending}>Cancel</Button>
        <Button loading={remove.isPending} onClick={() => deleteAccount && remove.mutate(deleteAccount.id)}>Delete account</Button>
      </>}>
        <p>This account will no longer appear in the institutional account list. This action cannot be undone from the dashboard.</p>
        {remove.isError && <p className="form-error" role="alert">{remove.error.message}</p>}
      </Modal>
      <Modal
        open={Boolean(resetAccount)}
        onClose={closeReset}
        title={temporaryPassword ? "Temporary password created" : "Reset account password"}
        description={
          temporaryPassword
            ? "Copy this password now. It will not be shown again."
            : `This will revoke ${resetAccount?.name || "the user"}'s existing sessions and replace their password.`
        }
        footer={
          temporaryPassword ? (
            <>
              <Button
                variant="secondary"
                onClick={() => void navigator.clipboard.writeText(temporaryPassword)}
              >
                Copy password
              </Button>
              <Button onClick={closeReset}>Done</Button>
            </>
          ) : (
            <>
              <Button variant="ghost" onClick={closeReset}>Cancel</Button>
              <Button
                loading={reset.isPending}
                onClick={() => resetAccount && reset.mutate({ id: resetAccount.id, scope: resetAccount.scope })}
              >
                Issue temporary password
              </Button>
            </>
          )
        }
      >
        {temporaryPassword ? (
          <div className="security-note" role="status">
            <KeyRound />
            <div>
              <strong>{temporaryPassword}</strong>
              <p>The user must change this immediately after signing in.</p>
            </div>
          </div>
        ) : (
          <div className="security-note">
            <KeyRound />
            <p>The existing password cannot be recovered. Only a replacement can be issued.</p>
          </div>
        )}
        {reset.isError && <p className="form-error" role="alert">{reset.error.message}</p>}
      </Modal>
    </div>
  );
}
