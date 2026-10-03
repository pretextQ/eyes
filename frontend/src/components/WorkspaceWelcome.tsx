import { Plug } from "lucide-react";
import { Link } from "react-router-dom";
import { useConnection } from "../connection";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";

export function WorkspaceWelcome() {
  const { openConnection } = useConnection();
  return (
    <section className="connection-empty" aria-label="项目未连接">
      <Empty className="min-h-[min(440px,60dvh)]">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <Plug />
          </EmptyMedia>
          <EmptyTitle>连接项目</EmptyTitle>
          <EmptyDescription>
            输入项目令牌，查看实验和执行记录。
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button onClick={openConnection}>连接项目</Button>
          <Button
            variant="link"
            nativeButton={false}
            render={<Link to="/guide" />}
          >
            查看接入指南
          </Button>
        </EmptyContent>
      </Empty>
    </section>
  );
}
