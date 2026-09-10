import os
import json
import random
import concurrent.futures
import pandas as pd

def get_random_name():
    adjectives = ["Alpha", "Brave", "Cosmic", "Dark", "Eagle", "Fast", "Gold", "Hyper", "Iron", "Jade"]
    nouns = ["Trader", "Bot", "Bull", "Bear", "Pioneer", "Runner", "Stalker", "Viper", "Wolf", "Zenith"]
    return f"{random.choice(adjectives)}_{random.choice(nouns)}_{random.randint(100, 999)}"

def create(model_name):
    try:
        with open("model_registry.json", "r") as f:
            data = json.load(f)
            alive_models = data.get("alive_models", [])
            model_weights = data.get("weights", {})
    except FileNotFoundError:
        alive_models = []
        model_weights = {}
        
    weights = [random.uniform(-1.0, 1.0) for _ in range(7)]
    
    if model_name not in alive_models:
        alive_models.append(model_name)
    model_weights[model_name] = weights
    
    with open("model_registry.json", "w") as f:
        json.dump({"alive_models": alive_models, "weights": model_weights}, f, indent=4)
        
    return weights

def reproduction(parent1_name, parent2_name, child_name):
    with open("model_registry.json", "r") as f:
        data = json.load(f)
        alive_models = data.get("alive_models", [])
        model_weights = data.get("weights", {})
        
    w1 = model_weights.get(parent1_name, [0]*7)
    w2 = model_weights.get(parent2_name, [0]*7)
    
    child_weights = []
    for a, b in zip(w1, w2):
        avg = (a + b) / 2.0
        perturbation = random.gauss(0, 0.02)
        child_weights.append(avg + perturbation)
        
    lineage_record = {
        "child": child_name,
        "parent1": {"name": parent1_name, "weights": w1},
        "parent2": {"name": parent2_name, "weights": w2},
        "child_weights": child_weights
    }
    
    try:
        with open("lineage_registry.json", "r") as f:
            lineages = json.load(f)
    except FileNotFoundError:
        lineages = []
    lineages.append(lineage_record)
    with open("lineage_registry.json", "w") as f:
        json.dump(lineages, f, indent=4)
        
    if child_name not in alive_models:
        alive_models.append(child_name)
    model_weights[child_name] = child_weights
    
    with open("model_registry.json", "w") as f:
        json.dump({"alive_models": alive_models, "weights": model_weights}, f, indent=4)
        
    return child_weights

def evaluate_single_model(model_name, weights, prices):
    cash = 1000.0
    stocks_owned = 0
    is_dead = False
    action_log = []
    final_price = prices[-1]
    
    for i in range(len(prices) - 5):
        window = prices[i:i+5]
        current_price = window[-1]
        
        # Continuous infrastructure / compute cost per step
        cash -= 0.05
        
        # If cash dips below zero, auto-sell a stock if available to cover the deficit
        if cash < 0:
            if stocks_owned > 0:
                cash += current_price
                stocks_owned -= 1
            else:
                is_dead = True
                action_log.append({
                    "step": i, "price": current_price, "action": "DEATH_INFRA_COST",
                    "cash": cash, "stocks_owned": stocks_owned, "score": 0.0
                })
                break
            
        inputs = window + [cash, float(stocks_owned)]
        score = sum(inp * w for inp, w in zip(inputs, weights))
        
        action = "HOLD"
        if score > 0.1:
            if cash >= current_price:
                cash -= current_price
                stocks_owned += 1
                action = "BUY"
            else:
                action = "HOLD_CANT_AFFORD"
        elif score < -0.1:
            if stocks_owned > 0:
                cash += current_price
                stocks_owned -= 1
                action = "SELL"
                
        total_net_worth = cash + (stocks_owned * current_price)
        if total_net_worth <= 0:
            is_dead = True
            action_log.append({
                "step": i, "price": current_price, "action": "DEATH_BANKRUPT",
                "cash": cash, "stocks_owned": stocks_owned, "score": score
            })
            break
                
        action_log.append({
            "step": i, "price": current_price, "action": action,
            "cash": cash, "stocks_owned": stocks_owned, "score": score
        })
        
    if not is_dead:
        cash += stocks_owned * final_price
        status = "survived"
    else:
        status = "dead"
        
    return model_name, {
        "cash": cash,
        "stocks_owned": 0 if not is_dead else stocks_owned,
        "final_net_worth": cash if not is_dead else cash + (stocks_owned * prices[-1]),
        "status": status,
        "action_log": action_log
    }

def game():
    with open("synthetic_stock_prices.txt", "r") as f:
        prices = [float(line.strip()) for line in f if line.strip()]
        
    with open("model_registry.json", "r") as f:
        registry = json.load(f)
        alive_models = registry.get("alive_models", [])
        weights_dict = registry.get("weights", {})
        
    portfolios = {}
    survivors = []
    dead_models = []
    all_logs = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(evaluate_single_model, name, weights_dict[name], prices): name 
            for name in alive_models if name in weights_dict
        }
        
        for future in concurrent.futures.as_completed(futures):
            model_name, result = future.result()
            log = result.pop("action_log")
            portfolios[model_name] = result
            
            if result["status"] == "survived":
                survivors.append(model_name)
            else:
                dead_models.append(model_name)
                
            for entry in log:
                entry["model_name"] = model_name
                all_logs.append(entry)
                
    simulation_results = {
        "portfolios": portfolios,
        "survivors": survivors,
        "dead": dead_models,
        "raw_logs": all_logs
    }
    
    return simulation_results

def evolve_pipeline(total_generations=100, target_population=8):
    output_dir = "simulation_output"
    agents_dir = os.path.join(output_dir, "agents_json")
    os.makedirs(agents_dir, exist_ok=True)
    
    with open("model_registry.json", "w") as f:
        json.dump({"alive_models": [], "weights": {}}, f)
    with open("lineage_registry.json", "w") as f:
        json.dump([], f)
        
    print("--- Starting Generation 1 ---")
    for _ in range(target_population):
        create(get_random_name())
        
    master_logs = []
    ultimate_best_model = None
    max_net_worth = -1.0
        
    for gen in range(1, total_generations + 1):
        results = game() 
        portfolios = results["portfolios"]
        
        for name, port in portfolios.items():
            safe_name = name.replace(" ", "_")
            agent_file_path = os.path.join(agents_dir, f"{safe_name}.json")
            
            agent_history = []
            if os.path.exists(agent_file_path):
                try:
                    with open(agent_file_path, "r") as af:
                        agent_history = json.load(af)
                except json.JSONDecodeError:
                    agent_history = []
            
            agent_gen_record = {
                "generation": gen,
                "status": port["status"],
                "final_net_worth": port["final_net_worth"],
                "cash": port["cash"],
                "stocks_owned": port["stocks_owned"],
                "actions": [log for log in results["raw_logs"] if log["model_name"] == name]
            }
            agent_history.append(agent_gen_record)
            
            with open(agent_file_path, "w") as af:
                json.dump(agent_history, af, indent=4)
        
        gen_df = pd.DataFrame(results["raw_logs"])
        if not gen_df.empty:
            gen_df["generation"] = gen
            gen_df["step"] = pd.to_numeric(gen_df["step"], downcast="integer")
            gen_df["price"] = pd.to_numeric(gen_df["price"], downcast="float")
            gen_df["cash"] = pd.to_numeric(gen_df["cash"], downcast="float")
            gen_df["stocks_owned"] = pd.to_numeric(gen_df["stocks_owned"], downcast="integer")
            gen_df["score"] = pd.to_numeric(gen_df["score"], downcast="float")
            gen_df["action"] = gen_df["action"].astype("category")
            gen_df["model_name"] = gen_df["model_name"].astype("category")
            master_logs.append(gen_df)
        
        all_evaluated = sorted(
            portfolios.items(), 
            key=lambda x: x[1]["final_net_worth"], 
            reverse=True
        )
        
        print(f"Gen {gen:3d} | Total Evaluated: {len(all_evaluated)}")
        if all_evaluated:
            top_name, top_port = all_evaluated[0]
            print(f"          | Top Performer: {top_name} ({top_port['final_net_worth']:.2f})")
            
            if top_port["final_net_worth"] > max_net_worth:
                max_net_worth = top_port["final_net_worth"]
                ultimate_best_model = top_name
                
        if gen == total_generations:
            print("\nEvolution complete!")
            break
            
        parent1 = all_evaluated[0][0]
        parent2 = all_evaluated[1][0] if len(all_evaluated) > 1 else parent1

        surviving_elite = [model_name for model_name, _ in all_evaluated[:target_population - 2]]
        next_gen_models = list(surviving_elite)
        
        with open("model_registry.json", "r") as f:
            current_registry = json.load(f)
        surviving_weights = {name: current_registry["weights"][name] for name in surviving_elite if name in current_registry["weights"]}
        
        agent_counter = 1
        while len(next_gen_models) < target_population:
            child_name = f"Offspring_{gen}_{agent_counter}"
            reproduction(parent1, parent2, child_name)
            next_gen_models.append(child_name)
            agent_counter += 1
                
        with open("model_registry.json", "r") as f:
            updated_data = json.load(f)
            
        updated_data["alive_models"] = next_gen_models
        updated_data["weights"] = surviving_weights
        
        with open("lineage_registry.json", "r") as f:
            lineages = json.load(f)
        for lin in lineages:
            if lin["child"] in next_gen_models:
                updated_data["weights"][lin["child"]] = lin["child_weights"]
                
        with open("model_registry.json", "w") as f:
            json.dump(updated_data, f, indent=4)

    if master_logs:
        compressed_master_df = pd.concat(master_logs, ignore_index=True)
        csv_path = os.path.join(output_dir, "compressed_simulation_logs.csv")
        compressed_master_df.to_csv(csv_path, index=False)
        print(f"\nCompressed master logs saved to '{csv_path}'")

    if ultimate_best_model:
        with open("model_registry.json", "r") as f:
            reg = json.load(f)
        champion_weights = reg["weights"].get(ultimate_best_model)
        
        if champion_weights:
            reg["weights"]["Agent 2"] = champion_weights
            if "Agent 2" not in reg["alive_models"]:
                reg["alive_models"].append("Agent 2")
                
            with open("model_registry.json", "w") as f:
                json.dump(reg, f, indent=4)
                
            print(f"Ultimate Champion '{ultimate_best_model}' tagged as 'Agent 2' with Net Worth: {max_net_worth:.2f}")

if __name__ == "__main__":
    evolve_pipeline(total_generations=100, target_population=8)
