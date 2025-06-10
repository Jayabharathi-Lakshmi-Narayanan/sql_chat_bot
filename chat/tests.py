from sql_agent import get_sql_agent

if __name__ == "__main__":
    question = "Show me all users"
    agent = get_sql_agent(question)
    result = agent.invoke({"input": question})
    print(result)
