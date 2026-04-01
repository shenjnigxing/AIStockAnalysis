import { PageState } from "../../lib/view-state";

const labels: Record<PageState, string> = {
  loading: "加载中",
  empty: "空数据",
  error: "错误",
  partial_error: "部分异常",
  ready: "就绪"
};

export function PageStateBanner({
  state,
  detail
}: {
  state: PageState;
  detail?: string;
}) {
  return (
    <div className={`stateBanner state-${state}`}>
      <strong>页面状态：</strong> {labels[state]}
      {detail ? <span> | {detail}</span> : null}
    </div>
  );
}
