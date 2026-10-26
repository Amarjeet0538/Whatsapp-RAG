import type { GroupSummary } from "../types";
import ThemeToggle from "./ThemeToggle";
import s from "./GroupSidebar.module.css";

type Props = {
  groups: GroupSummary[];
  selected: string | null;
  onSelect: (id: string) => void;
  onImport: () => void;
};

export default function GroupSidebar({ groups, selected, onSelect, onImport }: Props) {
  return (
    <nav className={s.sidebar} aria-label="Imported chats">
      <h2 className={s.title}>Chats</h2>
      <ul className={s.list}>
        {groups.map((g) => (
          <li key={g.wa_group_id}>
            <button
              type="button"
              className={s.item}
              aria-current={g.wa_group_id === selected ? "true" : undefined}
              onClick={() => onSelect(g.wa_group_id)}
            >
              <span className={s.name}>{g.name || g.wa_group_id}</span>
              <span className={s.meta}>
                <span className="num">{g.message_count}</span> messages,{" "}
                <span className="num">{g.member_count}</span> members
              </span>
            </button>
          </li>
        ))}
      </ul>
      <div className={s.footer}>
        <button type="button" className="btn btn-primary" onClick={onImport}>
          Import chat
        </button>
        <ThemeToggle />
      </div>
    </nav>
  );
}
