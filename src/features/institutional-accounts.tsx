import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus, UserRoundCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import {
  Badge,
  Button,
  ErrorState,
  LoadingState,
  PageHeader,
} from "../components/ui";
import {
  chapelGroupService,
  institutionalAccountService,
} from "../services/chapelflow";

const roles = [
  ["CHAPLAIN", "Chaplain"],
  ["STUDENT_CHAPLAIN", "Student Chaplain"],
  ["UNIT_HEAD", "Unit leader"],
  ["FELLOWSHIP_LEADER", "Fellowship leader"],
  ["ATTENDANCE_USHER", "Attendance usher"],
] as const;

export function InstitutionalAccountsPage() {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
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
  const update = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      institutionalAccountService.update(id, { is_active }),
    onSuccess: refresh,
  });
  const reset = useMutation({
    mutationFn: institutionalAccountService.resetPassword,
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    create.mutate({
      first_name: String(data.get("first_name")),
      last_name: String(data.get("last_name")),
      email: String(data.get("email")),
      password: String(data.get("password")),
      role: String(data.get("role")) as (typeof roles)[number][0],
      password_change_required: true,
      institutional_group: String(data.get("institutional_group")) || null,
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
          <Button icon={<Plus />} onClick={() => setOpen((value) => !value)}>
            Create account
          </Button>
        }
      />
      {open && (
        <form className="panel form-grid" onSubmit={submit}>
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
            <input name="email" type="email" required />
          </label>
          <label className="field">
            <span>Initial password</span>
            <input name="password" type="password" minLength={12} required />
          </label>
          <label className="field">
            <span>Role</span>
            <select name="role">
              {roles.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Unit or fellowship</span>
            <select name="institutional_group" disabled={groups.isPending}>
              <option value="">Not assigned</option>
              {groups.data
                ?.filter((group) => group.is_active)
                .map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name} · {group.group_type.toLowerCase()}
                  </option>
                ))}
            </select>
          </label>
          <div>
            <Button type="submit" loading={create.isPending}>
              Create securely
            </Button>
            {create.isError && <p role="alert">{create.error.message}</p>}
          </div>
        </form>
      )}
      <section className="table-panel">
        <header>
          <div className="panel-heading">
            <div>
              <h2>Chapel accounts</h2>
              <p>
                Only Super Admins can make changes. Passwords and tokens are
                never displayed.
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
                    onClick={() => reset.mutate(account.id)}
                  >
                    Reset password
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
