import { Command } from "cmdk";
import { ArrowUpRight, Plug, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { navigation, navigationGroups } from "../navigation";
import { Dialog } from "./ui";

export function QuickNavigation({
  onClose,
  onConnect,
}: {
  onClose: () => void;
  onConnect: () => void;
}) {
  const navigate = useNavigate();
  return (
    <Dialog
      title="快速导航"
      subtitle="查找页面，或打开连接设置。"
      onClose={onClose}
    >
      <Command className="quick-navigation" label="快速导航" loop>
        <div className="command-search">
          <Search size={18} aria-hidden="true" />
          <Command.Input
            data-autofocus
            placeholder="搜索页面或操作…"
            aria-label="搜索页面或操作"
          />
          <kbd>Esc</kbd>
        </div>
        <Command.List>
          <Command.Empty>没有找到相关页面，试试“实验”或“Agent”。</Command.Empty>
          {navigationGroups.map((group) => (
            <Command.Group key={group} heading={group}>
              {navigation
                .filter((item) => item.group === group)
                .map((item) => (
                  <Command.Item
                    key={item.url}
                    value={item.url}
                    keywords={[item.text, item.en, item.description]}
                    onSelect={() => {
                      onClose();
                      navigate(item.url);
                    }}
                  >
                    <item.icon size={18} aria-hidden="true" />
                    <span>
                      <strong>{item.text}</strong>
                      <small>{item.description}</small>
                    </span>
                    <ArrowUpRight size={15} aria-hidden="true" />
                  </Command.Item>
                ))}
              {group === "工作空间" && (
                <Command.Item
                  value="connection"
                  keywords={["连接", "设置", "令牌", "token"]}
                  onSelect={onConnect}
                >
                  <Plug size={18} aria-hidden="true" />
                  <span>
                    <strong>连接设置</strong>
                    <small>使用项目令牌连接实验空间</small>
                  </span>
                  <ArrowUpRight size={15} aria-hidden="true" />
                </Command.Item>
              )}
            </Command.Group>
          ))}
        </Command.List>
        <div className="command-footer">
          <span>
            <kbd>↑</kbd> <kbd>↓</kbd> 选择
          </span>
          <span>
            <kbd>↵</kbd> 打开
          </span>
        </div>
      </Command>
    </Dialog>
  );
}
