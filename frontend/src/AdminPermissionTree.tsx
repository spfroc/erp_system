import {
  ADMIN_PERMISSION_TREE,
  leafPermissionActive,
  modulePermissionState,
  toggleAdminPermissionLeaf,
  toggleAdminPermissionModule,
  type AdminPermissionModule,
} from "./adminPermissions";
import type { PermissionKey } from "./types";

type Props = {
  selected: PermissionKey[];
  onChange: (next: PermissionKey[]) => void;
  className?: string;
};

export function AdminPermissionTree({ selected, onChange, className = "" }: Props) {
  return (
    <div className={`admin-perm-tree ${className}`.trim()}>
      {ADMIN_PERMISSION_TREE.map((section) => (
        <div key={section.title} className="admin-perm-section">
          <div className="admin-perm-section-title">{section.title}</div>
          <div className="admin-perm-section-modules">
            {section.modules.map((mod) => (
              <AdminPermissionModuleBlock
                key={mod.id}
                module={mod}
                selected={selected}
                onChange={onChange}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function AdminPermissionModuleBlock({
  module,
  selected,
  onChange,
}: {
  module: AdminPermissionModule;
  selected: PermissionKey[];
  onChange: (next: PermissionKey[]) => void;
}) {
  const visible = module.children.filter((leaf) => !leaf.treeHidden);
  const state = modulePermissionState(selected, module);
  return (
    <div className="admin-perm-module">
      <label className="admin-perm-parent">
        <input
          type="checkbox"
          checked={state === "all"}
          ref={(el) => {
            if (el) el.indeterminate = state === "some";
          }}
          onChange={(event) => onChange(toggleAdminPermissionModule(selected, module, event.target.checked))}
        />
        <span>
          <strong>{module.label}</strong>
          {module.description ? <em>{module.description}</em> : null}
        </span>
      </label>
      <div className="admin-perm-children">
        {visible.map((leaf) => (
          <label key={leaf.key} className="admin-perm-child" title={leaf.hint || leaf.key}>
            <input
              type="checkbox"
              checked={leafPermissionActive(selected, leaf.key)}
              onChange={(event) => onChange(toggleAdminPermissionLeaf(selected, leaf.key, event.target.checked))}
            />
            <span>
              <strong>{leaf.label}</strong>
              {leaf.hint ? <em>{leaf.hint}</em> : null}
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}
