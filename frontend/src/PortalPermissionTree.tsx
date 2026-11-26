import {
  permissionGroupState,
  permissionLeafActive,
  portalPermissionTree,
  syncPortalAccountPermissions,
  togglePortalPermissionGroup,
  type PortalPermission,
} from "./portalPermissions";

type Props = {
  selected: string[];
  onChange: (next: string[]) => void;
  /** 可勾选上限；不传则全部可勾 */
  allowedIds?: string[] | null;
  /** 整棵树只读（如商品未启用裁剪时的预览） */
  readOnly?: boolean;
  /** 强制全部视为已选（兼容全开预览） */
  forceAllChecked?: boolean;
  className?: string;
};

export function PortalPermissionTree({
  selected,
  onChange,
  allowedIds = null,
  readOnly = false,
  forceAllChecked = false,
  className = "",
}: Props) {
  const tree = portalPermissionTree();
  const allowSet = allowedIds == null ? null : new Set(allowedIds);

  function isAllowed(id: string) {
    return allowSet == null || allowSet.has(id);
  }

  function leafChecked(id: string) {
    if (forceAllChecked) return true;
    return permissionLeafActive(selected, id);
  }

  function groupState(childIds: string[]) {
    if (forceAllChecked) return "all" as const;
    return permissionGroupState(selected, childIds);
  }

  return (
    <div className={`portal-perm-tree ${className}`.trim()}>
      {tree.map((group) => {
        const childIds = group.children.map((item) => item.id);
        const state = groupState(childIds);
        const groupAllowed = childIds.some((id) => isAllowed(id));
        const groupDisabled = readOnly || (!groupAllowed && state === "none");
        return (
          <div key={group.title} className="portal-perm-tree-group">
            <label className="portal-perm-tree-parent">
              <input
                type="checkbox"
                checked={state === "all"}
                ref={(el) => {
                  if (el) el.indeterminate = state === "some";
                }}
                disabled={groupDisabled}
                onChange={(event) => {
                  if (readOnly) return;
                  onChange(togglePortalPermissionGroup(selected, childIds, event.target.checked, allowedIds));
                }}
              />
              <span>
                <strong>{group.title}</strong>
                <em>{group.description}</em>
              </span>
            </label>
            <div className="portal-perm-tree-children">
              {group.children.map((option) => {
                const allowed = isAllowed(option.id);
                const checked = leafChecked(option.id);
                const disabled = readOnly || (!allowed && !checked);
                return (
                  <label key={option.id} className="portal-perm-tree-child">
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={disabled}
                      onChange={(event) => {
                        if (readOnly) return;
                        onChange(syncPortalAccountPermissions(selected, option.id, event.target.checked));
                      }}
                    />
                    <span>
                      <strong>
                        {option.label}
                        {!allowed ? "（套餐未包含）" : ""}
                      </strong>
                      <em>{option.hint}</em>
                    </span>
                  </label>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export type { PortalPermission };
