<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useOffline } from '../composables/useOffline'
import { getUser, followUser, unfollowUser } from '../api/users'
import { getArticles } from '../api/articles'
import { useUserStore } from '../stores/useUserStore'
import { useTauri } from '../composables/useTauri'
import { useBookmarkToggle } from '../composables/useBookmarkToggle'
import { useAsyncResource } from '../composables/useAsyncResource'
import ArticleCard from '../components/ArticleCard.vue'
import ReputationBadges from '../components/ReputationBadges.vue'
import type { UserProfile, ArticleSummary } from '../api/types'
import {
  UsersRound,
  UserCheck,
  BookOpen,
  MapPin,
  Mail,
  Edit,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const tauri = useTauri()
const { t } = useI18n()
const { canRead, canWrite, getFallback } = useOffline()

const canViewFollowGraph = computed(() => canRead('user.follow_graph'))

const id = computed(() => route.params.id as string)

// In local mode (Tauri or browser-local), use local account data.
const isSelf = computed(() => userStore.viewer?.id === id.value)
const isLocal = computed(() => userStore.isTauriMode || userStore.isBrowserLocal)

function _localUserToProfile(a: { id: string; username: string }): UserProfile {
  return {
    id: a.id,
    username: a.username,
    name: a.username,
    anonymous_name: '',
    affiliation: '',
    expertise: [],
    reputation: { professionalism: 0, objectivity: 0, collaboration: 0, pedagogy: 0 },
    followers_count: 0,
    following_count: 0,
    article_count: 0,
    created_at: new Date().toISOString(),
  }
}

const { data: user, loading, error, execute: loadUser } = useAsyncResource(
  async () => {
    // Self in local mode — use viewer profile directly.
    if (isLocal.value && isSelf.value && userStore.viewer) return userStore.viewer
    // Other user in local mode — look up from browser-local accounts.
    if (isLocal.value && !isSelf.value) {
      const accts = await tauri.listAccounts()
      if (accts && !('error' in accts) && Array.isArray(accts)) {
        const found = accts.find(a => a.id === id.value)
        if (found) return _localUserToProfile(found)
      }
      throw new Error('User not found')
    }
    return getUser(id.value)
  },
  null as UserProfile | null,
  { immediate: true },
)

const articles = ref<ArticleSummary[]>([])

const { toggle: handleToggleBookmark } = useBookmarkToggle(articles)

const isFollowing = ref(false)
const followLoading = ref(false)

// Load initial follow state from browser-local backend in local mode.
async function loadFollowState() {
  if (!isLocal.value || !userStore.viewer) return
  const r = await tauri.isFollowing({ follower_id: userStore.viewer.id, followed_id: id.value })
  if (r && !('error' in r)) {
    isFollowing.value = r.following
  }
}

async function handleFollow() {
  if (!userStore.viewer) return
  followLoading.value = true
  try {
    if (isLocal.value) {
      if (isFollowing.value) {
        await tauri.unfollowUser({ follower_id: userStore.viewer.id, followed_id: id.value })
      } else {
        await tauri.followUser({ follower_id: userStore.viewer.id, followed_id: id.value })
      }
    } else {
      if (isFollowing.value) {
        await unfollowUser(id.value)
      } else {
        await followUser(id.value)
      }
    }
    isFollowing.value = !isFollowing.value
  } catch { /* ignore */ }
  finally { followLoading.value = false }
}

async function loadArticles() {
  const merged: ArticleSummary[] = []

  // 1. Server articles (skip in pure Tauri mode — server won't respond)
  if (!tauri.isTauri.value) {
    try {
      const artData = await getArticles({ author_id: id.value, page: 1, size: 50 })
      const serverArticles = Array.isArray(artData) ? artData : (artData.articles ?? [])
      merged.push(...serverArticles)
    } catch { /* server unreachable in Tauri offline mode */ }
  }

  // 2. Tauri local drafts (only for current user's own page)
  if ((tauri.isTauri.value || tauri.isBrowserLocal.value) && isSelf.value) {
    try {
      const drafts = await tauri.listDrafts({ account_id: id.value })
      // TODO(tech-debt): drafts can be null or {error:string} — add null guard
      // and error-shape check before iterating (vue-tsc TS2488/TS18047)
      for (const d of drafts) {
        // Avoid duplicates — skip if already loaded from server
        if (!merged.some(a => a.id === d.id)) {
          // Try to get actual commit hash from local git
          let hash = ''
          try {
            const history = await tauri.gitHistory({ article_id: d.id })
            if (history && !('error' in history) && Array.isArray(history) && history.length > 0) {
              hash = history[0].hash
            }
          } catch { /* optional */ }
          // TODO(tech-debt): push object doesn't satisfy ArticleSummary — field types
          // inferred as 'any' because drafts union includes {error:string} (TS2345)
          merged.push({
            id: d.id,
            title: d.title || 'Untitled',
            status: 'draft',
            authors: [{ id: id.value, name: user.value?.name || id.value, anonymous_name: '' }],
            content_preview: '',
            commit_hash: hash,
            fork_count: 0,
            forked_from: null,
            commit_count: 0,
            score: null,
            days_remaining: null,
            sink_duration_days: null,
            is_bookmarked: false,
            is_own_article: true,
            created_at: d.updated_at,
            updated_at: d.updated_at,
          })
        }
      }
    } catch { /* Tauri drafts unavailable */ }
  }

  articles.value = merged
}

// Load articles after user fetch completes (sequential)
watch(user, (u) => {
  if (u) { loadArticles(); loadFollowState() }
}, { immediate: true })

// TODO(tech-debt): showFollowers, showFollowing, followers, following are
// never declared — this block will throw ReferenceError at runtime.
// Either declare the refs or remove the dead watch (route change already
// triggers user reload via useAsyncResource + watch(user, ...)).
watch(() => route.params.id, () => {
  showFollowers.value = false
  showFollowing.value = false
  followers.value = []
  following.value = []
  loadUser()
  loadArticles()
})


</script>

<template>
  <div class="user-page animate-fade-in">
    <!-- Loading -->
    <div v-if="loading" class="space-y-4 animate-pulse">
      <div class="flex items-start gap-4 mb-6">
        <div class="skeleton w-16 h-16 rounded-full shrink-0" />
        <div class="space-y-2 flex-1">
          <div class="skeleton h-7 w-1/3" />
          <div class="skeleton h-4 w-1/4" />
          <div class="skeleton h-4 w-1/5" />
        </div>
      </div>
    </div>

    <template v-else-if="user">
      <!-- Profile header -->
      <div class="bg-card border border-divider rounded-lg p-6 mb-6">
        <div class="flex flex-col sm:flex-row items-start gap-5">
          <!-- Avatar -->
          <div class="w-16 h-16 rounded-full bg-[#21262d] flex items-center justify-center shrink-0 border border-divider overflow-hidden">
            <img
              v-if="user.avatar_url"
              :src="user.avatar_url"
              :alt="user.name"
              class="w-full h-full object-cover"
            />
            <span v-else class="text-xl font-heading font-bold text-ink-muted">
              {{ (user.name || '?')[0].toUpperCase() }}
            </span>
          </div>

          <div class="flex-1 min-w-0">
            <!-- Name -->
            <h1 class="text-display-md font-heading font-bold text-ink mb-0.5">
              {{ user.name }}
            </h1>

            <!-- Anonymous name (only visible to self) -->
            <p v-if="isSelf" class="text-xs text-ink-muted mb-2">
              {{ t('user.anonymousName') }}: <span class="font-mono text-ink">{{ user.anonymous_name }}</span>
            </p>

            <!-- Affiliation & Contact -->
            <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-muted mb-3">
              <span v-if="user.affiliation" class="flex items-center gap-1">
                <MapPin class="w-3 h-3" stroke-width="2" />
                {{ user.affiliation }}
              </span>
              <span v-if="user.contact" class="flex items-center gap-1">
                <Mail class="w-3 h-3" stroke-width="2" />
                {{ user.contact }}
              </span>
              <span class="flex items-center gap-1">
                <BookOpen class="w-3 h-3" stroke-width="2" />
                {{ t('user.articlesCount', { count: user.article_count }) }}
              </span>
            </div>

            <!-- Stats row -->
            <div class="flex items-center gap-4 text-sm">
              <router-link
                v-if="canViewFollowGraph"
                :to="`/user/${user.id}/followers`"
                class="flex items-center gap-1.5 text-ink-muted hover:text-ink transition-colors no-underline"
              >
                <UsersRound class="w-3.5 h-3.5" stroke-width="2" />
                <span class="font-semibold">{{ user.followers_count }}</span>
                <span>{{ t('common.followers') }}</span>
              </router-link>
              <span
                v-else
                class="flex items-center gap-1.5 text-ink-muted/50 cursor-not-allowed"
                :data-tooltip="t(getFallback('user.follow_graph'))"
              >
                <UsersRound class="w-3.5 h-3.5" stroke-width="2" />
                <span class="font-semibold">{{ user.followers_count }}</span>
                <span>{{ t('common.followers') }}</span>
              </span>
              <router-link
                v-if="canViewFollowGraph"
                :to="`/user/${user.id}/following`"
                class="flex items-center gap-1.5 text-ink-muted hover:text-ink transition-colors no-underline"
              >
                <UserCheck class="w-3.5 h-3.5" stroke-width="2" />
                <span class="font-semibold">{{ user.following_count }}</span>
                <span>{{ t('common.following') }}</span>
              </router-link>
              <span
                v-else
                class="flex items-center gap-1.5 text-ink-muted/50 cursor-not-allowed"
                :data-tooltip="t(getFallback('user.follow_graph'))"
              >
                <UserCheck class="w-3.5 h-3.5" stroke-width="2" />
                <span class="font-semibold">{{ user.following_count }}</span>
                <span>{{ t('common.following') }}</span>
              </span>
            </div>
          </div>

          <!-- Follow/Unfollow button (viewing others) -->
          <button
            v-if="!isSelf && userStore.viewer"
            class="btn-sm shrink-0 transition-colors duration-200"
            :class="isFollowing
              ? 'btn-outline rounded-xl'
              : canWrite('user.follow_graph')
                ? 'bg-accent text-page hover:brightness-110 rounded-xl'
                : 'bg-[#21262d] text-ink-muted/50 cursor-not-allowed rounded-xl'"
            :disabled="followLoading || !canWrite('user.follow_graph')"
            :data-tooltip="!canWrite('user.follow_graph') ? t(getFallback('user.follow_graph')) : ''"
            @click="handleFollow"
          >
            {{ isFollowing ? t('common.following') : t('common.follow') }}
          </button>

          <!-- Edit profile button (self only) — coming soon -->
          <button
            v-if="isSelf"
            class="btn-outline btn-sm shrink-0 opacity-50 cursor-not-allowed"
            disabled
            :data-tooltip="t('common.comingSoon')"
          >
            <Edit class="w-3.5 h-3.5" stroke-width="2" />
            {{ t('common.editProfile') }}
          </button>
        </div>

        <!-- Expertise -->
        <div v-if="user.expertise?.length" class="flex flex-wrap gap-1.5 mt-4 pt-4 border-t border-divider">
          <span
            v-for="exp in user.expertise"
            :key="exp"
            class="px-2.5 py-0.5 text-xs text-ink-muted bg-[#21262d] rounded-full"
          >
            {{ exp }}
          </span>
        </div>

        <!-- Reputation -->
        <div v-if="user.reputation" class="mt-4 pt-4 border-t border-divider">
          <ReputationBadges :reputation="user.reputation" :show-label="true" />
        </div>
      </div>


      <!-- Articles section -->
      <div>
        <h2 class="text-lg font-heading font-semibold text-ink mb-4">
          {{ isSelf && isLocal ? t('user.myDrafts') : t('user.articlesTitle') }}
        </h2>

        <div v-if="articles.length === 0" class="card p-8 text-center">
          <p class="text-ink-muted text-sm">{{ t('common.noArticles') }}</p>
        </div>

        <div v-else class="space-y-4">
          <ArticleCard
            v-for="article in articles"
            :key="article.id"
            :article="article"
            @toggle-bookmark="handleToggleBookmark"
            @deleted="(id: string) => articles = articles.filter(a => a.id !== id)"
          />
        </div>
      </div>
    </template>

    <!-- Error state -->
    <div v-else class="card p-12 text-center">
      <p class="text-ink-muted">{{ t('user.notFound') }}</p>
    </div>
  </div>
</template>
