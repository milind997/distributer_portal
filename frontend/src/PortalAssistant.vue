<script setup>
import { ref, watch, nextTick } from 'vue';
import { Sparkles, X, Send, LoaderCircle } from 'lucide-vue-next';
import { request } from './api';
const props = defineProps({ partner: { type: String, default: '' }, manager: Boolean });
const opened = ref(false), question = ref(''), pending = ref(false), error = ref('');
const messages = ref([]), input = ref(null), transcript = ref(null), launcher = ref(null);
let generation = 0;
watch(() => props.partner, () => { generation++; messages.value = []; error.value = ''; pending.value = false; });
async function clearChat() {
 generation++;
 messages.value = []; question.value = ""; error.value = ""; pending.value = false;
 await nextTick(); input.value?.focus();
}
async function toggle() {
 opened.value = !opened.value;
 await nextTick();
 if(opened.value) input.value?.focus(); else launcher.value?.focus();
}
async function send(value = question.value) {
 if(pending.value || !value.trim()) return;
 if(props.manager && !props.partner) { error.value = 'Select a distributor at the top of the page first.'; return; }
 const current = generation;
 messages.value.push({role:'user', text:value.trim()});
 question.value = ''; error.value = ''; pending.value = true;
 await scroll();
 try {
  const result = await request('distributor_portal.assistant.ask', {question:value.trim(), partner:props.partner}, 'POST', true);
  if(current === generation) messages.value.push({role:'assistant', text:result.answer, source:result.distributor});
 } catch(e) { if(current === generation) error.value = e.message; }
 finally { if(current === generation) { pending.value = false; await scroll(); input.value?.focus(); } }
}
async function scroll() { await nextTick(); if(transcript.value) transcript.value.scrollTop = transcript.value.scrollHeight; }
</script>

<template>
 <div class="portal-assistant">
  <section v-if="opened" id="portal-assistant-chat" class="assistant-panel" role="dialog" aria-label="Portal assistant" @keydown.esc="toggle">
   <header class="assistant-header"><Sparkles :size="19"/><div><strong>Portal assistant</strong><small>Quick answers · Portal data</small></div><button class="assistant-clear" aria-label="Clear chat" title="Clear chat" @click="clearChat">Clear chat</button><button aria-label="Close assistant" @click="toggle"><X :size="19"/></button></header>
   <div ref="transcript" class="assistant-transcript" aria-live="polite" aria-relevant="additions">
    <div class="assistant-welcome"><strong>How can I help?</strong><p>Choose a question about your selected distributor. Answers are calculated from portal records.</p><small>Fixed questions · Read-only · No AI connection required.</small></div>
    <div v-if="!messages.length" class="assistant-prompts"><button v-for="prompt in ['Summarize my stock', 'Sales this month', 'Order status', 'Available credit', 'What should I reorder?', 'How do I record a sale?']" :key="prompt" @click="send(prompt)">{{ prompt }}</button></div>
    <article v-for="(message, index) in messages" :key="index" :class="['assistant-message', message.role]"><small>{{ message.role === 'user' ? 'You' : 'Portal assistant' }}</small><p>{{ message.text }}</p><small v-if="message.source" class="assistant-source">Source: {{ message.source }} · portal data</small></article>
    <p v-if="pending" class="assistant-pending"><LoaderCircle :size="15" class="assistant-spin"/> Preparing your answer…</p>
    <p v-if="error" class="assistant-error" role="alert">{{ error }}</p>
   </div>
   <form class="assistant-compose" @submit.prevent="send()"><input ref="input" v-model="question" aria-label="Ask the portal assistant" placeholder="Ask about stock, sales or orders…" maxlength="1200" :disabled="pending"/><button type="submit" aria-label="Send question" :disabled="pending || !question.trim()"><Send :size="18"/></button></form>
  </section>
  <button ref="launcher" class="assistant-launcher" :aria-expanded="opened" aria-controls="portal-assistant-chat" :aria-label="opened ? 'Close assistant panel' : 'Open portal assistant'" title="Portal assistant" @click="toggle"><X v-if="opened" :size="22"/><Sparkles v-else :size="23"/></button>
 </div>
</template>

<style scoped>
.portal-assistant { position:fixed; right:20px; bottom:20px; z-index:45; }
.assistant-launcher { display:grid; place-items:center; width:50px; height:50px; border-radius:50%; background:#234e83; color:white; border:1px solid #84a9d6; box-shadow:0 5px 20px #10243c40; }
.assistant-launcher:hover { background:#173b68; }
.assistant-panel { position:absolute; bottom:64px; right:0; width:min(380px,calc(100vw - 32px)); height:min(550px,calc(100dvh - 110px)); background:#fff; border:1px solid #cbd5e1; border-radius:16px; box-shadow:0 12px 50px #0f172a33; overflow:hidden; display:flex; flex-direction:column; }
.assistant-header { display:flex; align-items:center; gap:10px; padding:17px; background:#14243c; color:#fff; }
.assistant-header div { flex:1; }.assistant-header .assistant-clear { font-size:11px; white-space:nowrap; border:1px solid #58718f; border-radius:6px; padding:6px 8px; }.assistant-header small { display:block; color:#c7d8ed; margin-top:4px; font-size:10px; }.assistant-header button { display:grid; place-items:center; padding:5px; }
.assistant-transcript { flex:1; overflow:auto; padding:18px; min-height:0; }
.assistant-welcome { color:#243b58; line-height:1.6; }.assistant-welcome p { margin:8px 0; }.assistant-welcome small { color:#58677b; font-size:11px; }
.assistant-prompts { display:flex; flex-wrap:wrap; gap:7px; margin:16px 0; }.assistant-prompts button { border:1px solid #bdcde1; border-radius:16px; padding:8px 11px; color:#234e83; font-size:11px; background:#f2f6fc; }
.assistant-message { background:#eef3f9; border-radius:12px; margin:12px 0; padding:12px; color:#172b45; }.assistant-message.user { background:#234e83; color:white; margin-left:25px; }.assistant-message p { white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.6; margin-top:5px; font-size:12px; }.assistant-message > small { font-size:10px; font-weight:600; }.assistant-source { display:block; margin-top:10px; color:#526176; }
.assistant-compose { display:flex; gap:8px; border-top:1px solid #dbe3ee; padding:12px; }.assistant-compose input { flex:1; min-width:0; font-size:12px; }.assistant-compose button { border-radius:8px; padding:9px; background:#234e83; color:white; }
.assistant-pending { display:flex; align-items:center; gap:8px; color:#526176; font-size:12px; }.assistant-error { background:#fef2f2; color:#991b1b; padding:12px; border-radius:8px; font-size:12px; }.assistant-spin { animation:assistant-spin 1s linear infinite; }@keyframes assistant-spin { to {transform:rotate(360deg)} }
@media(max-width:850px) { .portal-assistant { right:16px; bottom:16px; } }
@media(prefers-reduced-motion:reduce) { .assistant-spin {animation:none} }
</style>
