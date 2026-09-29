// Tasks: add a task from the Workspace and see it on the open list, then complete it
// after its checklist step. Local stack only.
// node tools/acceptance/phase_b/p2_tasks_board.mjs
import { WS, OUT, closeAll, fits, load, must, open, recorder, sql } from './pw.mjs'

const { check, shot, finish } = recorder('p2_tasks_board')
const owner = load(process.env.LOCAH_ACCEPT_OWNER || `${OUT}/owner2.json`)
const as = must(owner.token)

const shop = (await as('/v1/platform/businesses', { method: 'POST', body: {
  display_name: 'Harbour Stay Tasks', business_type: 'other' } })).data.business
const bid = shop.id
await as('/v1/b/' + bid + '/modules/tasks/enable', { method: 'POST' })

const ctx = await open({ who: owner })
const page = ctx.page
try {
  await page.goto(`${WS}/b/${bid}/tasks`)
  await page.getByRole('heading', { name: 'Tasks', exact: true }).waitFor()
  await page.getByLabel('Title').fill('Turn room 12')
  await page.getByRole('button', { name: 'Add task' }).click()
  await page.getByRole('link', { name: 'Turn room 12' }).waitFor()
  const taskId = sql(`select id from tasks_tasks where business_id = '${bid}'`)
  check(taskId.length > 10, 'the task is saved')
  await shot(page, '01-open-task.png')
  await page.getByRole('link', { name: 'Turn room 12' }).click()
  await page.getByLabel('Checklist step').fill('Change linen')
  await page.getByRole('button', { name: 'Add step' }).click()
  await page.getByRole('button', { name: 'Mark done' }).click()
  await page.getByRole('button', { name: 'Undo' }).waitFor()
  await page.getByRole('button', { name: 'Complete task' }).click()
  await page.getByRole('button', { name: 'Complete task' }).waitFor({ state: 'detached' })
  await page.getByRole('link', { name: 'Completed' }).click()
  await page.getByRole('link', { name: 'Turn room 12' }).waitFor()
  const status = sql(`select status from tasks_tasks where id = '${taskId}'`)
  check(status === 'completed', `the task is completed (${status})`)
  await shot(page, '02-completed.png')
  check(await fits(page), 'the task list fits the desktop width')
  check(page.realErrors().length === 0, `no console errors (${page.realErrors().slice(0, 2).join(' | ')})`)
} finally {
  await ctx.context.close()
  await closeAll()
  finish()
}
