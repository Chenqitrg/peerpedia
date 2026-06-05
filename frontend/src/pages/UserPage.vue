<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getUser, getFollowers, getFollowing } from '../api/users'
import { getArticles } from '../api/articles'
import { useUserStore } from '../stores/useUserStore'
import { useBookmarkToggle } from '../composables/useBookmarkToggle'
import ArticleCard from '../components/ArticleCard.vue'
import type { UserProfile, ArticleSummary } from '../api/types'
import {
  Users,
  BookOpen,
  MapPin,
  Mail,
  Edit,
  ExternalLink,
  Star,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const id = computed(() => route.params.id as string)

const user = ref<UserProfile | null>(null)
const articles = ref<ArticleSummary[]>([])
const loading = ref(true)
const showFollowers = ref(false)
const showFollowing = ref(false)
const followers = ref<any[]>([])
const following = ref<any[]>([])

const { toggle: handleToggleBookmark } = useBookmarkToggle(articles)

const isSelf = computed(() => {
  return userStore.viewer?.id === id.value
})

onMounted(async () => {
  await loadUser()
})

watch(() => route.params.id, () => {
  showFollowers.value = false
  showFollowing.value = false
  followers.value = []
  following.value = []
  loadUser()
})

async function loadUser() {
  loading.value = true
  try {
    user.value = await getUser(id.value)
    // Load articles by this author
    const artData = await getArticles({ status: undefined, page: 1, size: 50 })
    const allArticles = Array.isArray(artData) ? artData : (artData.articles ?? [])
    articles.value = allArticles.filter((a: any) =>
      a.authors?.some((au: any) => au.id === id.value),
    )
  } catch (e) {
    console.error('Failed to load user:', e)
  } finally {
    loading.value = false
  }
}

async function loadFollowers() {
  if (followers.value.length) {
    showFollowers.value = !showFollowers.value
    return
  }
  try {
    followers.value = await getFollowers(id.value)
    showFollowers.value = true
  } catch (e) {
    console.error('Failed to load followers:', e)
  }
}

async function loadFollowing() {
  if (following.value.length) {
    showFollowing.value = !showFollowing.value
    return
  }
  try {
    following.value = await getFollowing(id.value)
    showFollowing.value = true
  } catch (e) {
    console.error('Failed to load following:', e)
  }
}

function goToEditProfile() {
  // Will navigate to profile edit page or open inline editor
}
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
              Anonymous name: <span class="font-mono text-ink">{{ user.anonymous_name }}</span>
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
                {{ user.article_count }} articles
              </span>
            </div>

            <!-- Stats row -->
            <div class="flex items-center gap-4 text-sm">
              <button
                class="flex items-center gap-1.5 text-ink-muted hover:text-ink transition-colors"
                @click="loadFollowers"
              >
                <Users class="w-3.5 h-3.5" stroke-width="2" />
                <span class="font-semibold">{{ user.followers_count }}</span>
                <span>followers</span>
              </button>
              <button
                class="flex items-center gap-1.5 text-ink-muted hover:text-ink transition-colors"
                @click="loadFollowing"
              >
                <Users class="w-3.5 h-3.5" stroke-width="2" />
                <span class="font-semibold">{{ user.following_count }}</span>
                <span>following</span>
              </button>
            </div>
          </div>

          <!-- Edit profile button (self only) -->
          <button
            v-if="isSelf"
            class="btn-outline btn-sm shrink-0"
            @click="goToEditProfile"
          >
            <Edit class="w-3.5 h-3.5" stroke-width="2" />
            Edit Profile
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

        <!-- Followers/Following expandable lists -->
        <div v-if="showFollowers && followers.length" class="mt-3 pt-3 border-t border-divider">
          <p class="text-xs text-ink-muted mb-2">Followers</p>
          <div class="flex flex-wrap gap-2">
            <router-link
              v-for="f in followers"
              :key="f.id"
              :to="`/user/${f.id}`"
              class="text-xs text-accent hover:text-accent-hover no-underline"
            >
              {{ f.name }}
            </router-link>
          </div>
        </div>
        <div v-if="showFollowing && following.length" class="mt-3 pt-3 border-t border-divider">
          <p class="text-xs text-ink-muted mb-2">Following</p>
          <div class="flex flex-wrap gap-2">
            <router-link
              v-for="f in following"
              :key="f.id"
              :to="`/user/${f.id}`"
              class="text-xs text-accent hover:text-accent-hover no-underline"
            >
              {{ f.name }}
            </router-link>
          </div>
        </div>

        <!-- Reputation -->
        <div v-if="user.reputation" class="mt-4 pt-4 border-t border-divider">
          <div class="flex items-center gap-1 text-xs text-ink-muted mb-3">
            <Star class="w-3 h-3" stroke-width="2" />
            <span class="font-semibold">Reputation</span>
          </div>
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div
              v-for="(value, key) in user.reputation"
              :key="key"
              class="text-center bg-[#0d1117] rounded-lg p-2.5 border border-divider"
            >
              <div class="text-lg font-bold text-accent font-mono">{{ value }}</div>
              <div class="text-xs text-ink-muted capitalize">{{ key }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Articles section -->
      <div>
        <h2 class="text-lg font-heading font-semibold text-ink mb-4">
          Articles
        </h2>

        <div v-if="articles.length === 0" class="card p-8 text-center">
          <p class="text-ink-muted text-sm">No articles yet.</p>
        </div>

        <div v-else class="space-y-4">
          <ArticleCard
            v-for="article in articles"
            :key="article.id"
            :article="article"
            @toggle-bookmark="handleToggleBookmark"
          />
        </div>
      </div>
    </template>

    <!-- Error state -->
    <div v-else class="card p-12 text-center">
      <p class="text-ink-muted">User not found.</p>
    </div>
  </div>
</template>
