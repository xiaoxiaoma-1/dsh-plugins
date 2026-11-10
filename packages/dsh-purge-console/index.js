// dsh-purge-console — host 侧空壳。
//
// 本插件的全部能力都在客户端（client.js）：往设置页左侧栏注册一个「破甲控制台」分节，
// 通过 dsh-purge 已有的同源 HTTP 接口读写状态。host 侧不注册工具、不接线，
// 所以这里只声明插件身份，保持 apply 为空。

export const name = 'dsh-purge-console';
export const inject = [];

export function apply() {
  // intentionally empty
}
