def scenario_game():
st.subheader("🧠 Word in Context")
st.write("Choose the sentence that uses the word appropriately in context.")


scenarios = {
"academic": "You are writing an academic essay.",
"daily": "You are talking with a friend.",
}


word = random.choice(vocab_data["word"].tolist())
scenario_type = random.choice(list(scenarios.keys()))


st.markdown(f"**Target word:** {word}")
st.info(scenarios[scenario_type])


sentence_bank = {
"analyze": [
("The researcher analyzed the data carefully.", "academic", True),
("I analyze very happy today.", "daily", False),
("The data was analyze by him yesterday.", "academic", False)
],
"conduct": [
("The team conducted a survey among students.", "academic", True),
("She conducted very fast to school.", "daily", False),
("They conduct happy yesterday.", "daily", False)
],
"impact": [
("Technology has a significant impact on education.", "academic", True),
("The movie impacted very fun.", "daily", False),
("Impact is big for happy people.", "daily", False)
],
"significant": [
("There was a significant difference between the two groups.", "academic", True),
("That sandwich is significant delicious.", "daily", False),
("He is significant run fast.", "daily", False)
]
}


options = [s[0] for s in sentence_bank[word]]
correct_sentence = [s[0] for s in sentence_bank[word] if s[2]][0]


choice = st.radio("Which sentence is appropriate?", options)


if st.button("Check Answer"):
if choice == correct_sentence:
st.success("✅ Correct! This sentence uses the word appropriately.")
else:
st.error("❌ Not quite. Pay attention to context and usage.")
