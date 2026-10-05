const path = require('node:path')
const root = path.resolve(__dirname, '../../marketing-site')
const createJestConfig = require('../../marketing-site/node_modules/next/jest')({ dir: root })
module.exports = createJestConfig({
  rootDir: root,
  roots: [root, __dirname],
  testEnvironment: 'jsdom',
  testMatch: [path.join(__dirname, 'presentation.test.cjs')],
  moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' },
  modulePaths: ['<rootDir>/node_modules'],
  modulePathIgnorePatterns: ['<rootDir>/.next/'],
  setupFilesAfterEnv: ['@testing-library/jest-dom'],
})