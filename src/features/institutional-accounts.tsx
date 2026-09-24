import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus, UserRoundCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
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
  chapelGroupService,
  institutionalAccountService,
} from "../services/chapelflow";
import { ApiError } from "../lib/api";

const roles = [
  ["CHAPLAIN", "Chaplain"],
  ["STUDENT_CHAPLAIN", "Student Chaplain"],
  ["UNIT_HEAD", "Unit leader"],
  ["FELLOWSHIP_LEADER", "Fellowship leader"],
  ["ATTENDANCE_USHER", "Attendance usher"],
] as const;

type InstitutionalRole = (typeof roles)[number][0];

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
  const [selectedRole, setSelectedRole] = useState<InstitutionalRole>("CHAPLAIN");
  const [selectedGroup, setSelectedGroup] = useState("");
  const [resetAccount, setResetAccount] = useState<{ id: string; name: string } | null>(null);
  const [temporaryPassword, setTemporaryPassword] = useState("");
  const accounts = useQuery({
    queryKey: ["institutional-accounts"],
    queryFn: async () => (await institutionalAccountService.list()).data,
  });
  const groups = useQuery({
    queryKey: ["chapel-groups", "institutional-accounts"],
    queryFn: async () => (await chapelGroupService.list()).data,
  });
  const refresh = () =>
    void client.invalidateQueries({ queryKey: ["institutional-accounts"] });
  const create = useMutation({
    mutationFn: institutionalAccountService.create,
    onSuccess: () => {
      setOpen(false);
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
    mutationFn: institutionalAccountService.resetPassword,
    onSuccess: (response) => {
      setTemporaryPassword(response.data.temporary_password);
      refresh();
    },
  });
  function closeReset() {
    if (reset.isPending) return;
    setResetAccount(null);
    setTemporaryPassword("");
    reset.reset();
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const role = String(data.get("role")) as InstitutionalRole;
    const groupType = roleGroupType(role);
    create.mutate({
      first_name: String(data.get("first_name")),
      last_name: String(data.get("last_name")),
      email: String(data.get("email")),
      password: String(data.get("password")),
      role,
      password_change_required: true,
      ...(groupType && selectedGroup ? { institutional_group: selectedGroup } : {}),
    });
  }
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
        description="Provision and safely manage chapel leadership and the two attendance usher accounts."
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
            <input name="password" type="password" minLength={12} required />
          </label>
          <label className="field">
            <span>Role</span>
            <select
              name="role"
              value={selectedRole}
              onChange={(event) => {
                setSelectedRole(event.target.value as InstitutionalRole);
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
          <label className="field">
            <span>Unit or fellowship</span>
            <select
              name="institutional_group"
              value={selectedGroup}
              disabled={groups.isPending || !roleGroupType(selectedRole)}
              required={Boolean(roleGroupType(selectedRole))}
              onChange={(event) => setSelectedGroup(event.target.value)}
              aria-invalid={Boolean(validationMessage(create.error, "institutional_group"))}
              aria-describedby="institutional-group-note institutional-group-error"
            >
              <option value="">
                {roleGroupType(selectedRole) ? "Select an assignment" : "Not applicable to this role"}
              </option>
              {groups.data
                ?.filter(
                  (group) =>
                    group.is_active &&
                    group.group_type === roleGroupType(selectedRole),
                )
                .map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name} · {group.group_type.toLowerCase()}
                  </option>
                ))}
            </select>
            <small id="institutional-group-note">
              {roleGroupType(selectedRole)
                ? "Leaders are assigned only to their matching unit or fellowship."
                : "Only Unit and Fellowship leaders are assigned to a chapel group."}
            </small>
            {validationMessage(create.error, "institutional_group") && (
              <small id="institutional-group-error" className="field__error" role="alert">
                {validationMessage(create.error, "institutional_group")}
              </small>
            )}
          </label>
          <div>
            <Button type="submit" loading={create.isPending}>
              Create securely
            </Button>
            {create.isError && !(create.error instanceof ApiError && create.error.fieldErrors) && (
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
                      })
                    }
                  >
                    Reset password
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
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
                onClick={() => resetAccount && reset.mutate(resetAccount.id)}
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
