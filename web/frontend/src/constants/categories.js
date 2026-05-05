export const CATEGORY_META = [
  { key: 'ai_ecosystem', label: 'AI生态', color: '#5F49D8' },
  { key: 'infra_and_tools', label: '开发工具', color: '#61BAFB' },
  { key: 'product_and_ui', label: '产品与UI', color: '#8B7AF5' },
  { key: 'knowledge_base', label: '知识库', color: '#22C55E' }
]

export const CATEGORY_LABEL_MAP = Object.fromEntries(
  CATEGORY_META.map((item) => [item.key, item.label])
)

export function getCategoryLabel(raw) {
  const key = String(raw || '')
  return CATEGORY_LABEL_MAP[key] || key || '未分类'
}
