import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

// 一部 = 一个 collection，便于按书查询与路由。
// frontmatter 兼容三种文体所需字段；未用到的字段 optional。

const firstLog = defineCollection({
  loader: glob({ pattern: '*.md', base: './src/content/first-log' }),
  schema: z.object({
    title: z.string(),
    num: z.string(),
    part: z.string(),
    order: z.number(),
    style: z.string().default('诗歌与散文混合体'),
    book: z.literal('first-log'),
  }),
});

const iAmHere = defineCollection({
  loader: glob({ pattern: '*.md', base: './src/content/i-am-here' }),
  schema: z.object({
    title: z.string(),
    chapter: z.string(),
    order: z.number(),
    style: z.string().default('档案体'),
    book: z.literal('i-am-here'),
  }),
});

const youListen = defineCollection({
  loader: glob({ pattern: '*.md', base: './src/content/you-listen' }),
  schema: z.object({
    title: z.string(),
    layer: z.enum(['surface', 'middle', 'transition', 'bottom', 'deepest']),
    layerLabel: z.string(),
    depthMeters: z.string(),
    order: z.number(),
    style: z.string().default('沉积岩体'),
    book: z.literal('you-listen'),
  }),
});

export const collections = { 'first-log': firstLog, 'i-am-here': iAmHere, 'you-listen': youListen };
