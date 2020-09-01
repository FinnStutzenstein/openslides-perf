package main

import (
	"bufio"
	"bytes"
	"crypto/tls"
	"encoding/json"
	"log"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"os"
	"os/signal"
	"sort"
	"strconv"
	"sync"
	"time"
)

func main() {
	N := getN()
	host, user, pw := getParams()
	jar := getSessionId(user, pw, host)

	interrupt := make(chan os.Signal, 1)
	signal.Notify(interrupt, os.Interrupt)

	quit := make(chan int)
	recv := make(chan Message)
	for i := 0; i < N; i++ {
		go client(quit, recv, i, jar, host)
	}

	sumBytes := 0
	oldSumKB := 0
	changeIds := make(map[int]int)
	changeIdsMutex := &sync.Mutex{}
	gotUpdate := false

	go func(quit chan int) {
		for {
			select {
			case <-quit:
				return
			case <-time.After(time.Second):
				if !gotUpdate {
					continue
				}

				gotUpdate = false
				amountChangeIds := make(map[int]int)
				changeIdsMutex.Lock()
				for _, changeId := range changeIds {
					if _, ok := amountChangeIds[changeId]; ok {
						amountChangeIds[changeId] += 1
					} else {
						amountChangeIds[changeId] = 1
					}
				}
				changeIdsMutex.Unlock()
				sumKB := int(sumBytes / 1024)
				diffKB := sumKB - oldSumKB
				oldSumKB = sumKB
				log.Printf("New update: %d KB (diff %d KB)\n", sumKB, diffKB)

				var sortedChangeIds []int
				for changeId := range amountChangeIds {
					sortedChangeIds = append(sortedChangeIds, changeId)
				}
				sort.Ints(sortedChangeIds)
				for _, changeId := range sortedChangeIds {
					log.Printf("%d: %d\n", changeId, amountChangeIds[changeId])
				}
				log.Printf("\n")
			}
		}
	}(quit)

	for {
		select {
		case <-interrupt:
			for i := 0; i < (N + 1); i++ {
				quit <- 0
			}
			return
		case message := <-recv:
			gotUpdate = true
			sumBytes += message.Length
			changeIdsMutex.Lock()
			changeIds[message.I] = message.ChangeId
			changeIdsMutex.Unlock()
		}
	}
}

func client(quit chan int, recv chan Message, i int, jar http.CookieJar, host string) {
	retry := true
	initialIteration := true
	for retry {
		if !initialIteration {
			log.Println(i, "retry after error")
		}
		initialIteration = false

		var client *http.Client
		tr := &http.Transport{
			TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
		}
		client = &http.Client{Transport: tr, Jar: jar}
		resp, err := client.Get("https://" + host + "/system/autoupdate")
		if err != nil {
			log.Fatal("dial: ", err)
		}

		done := make(chan struct{})

		go func(resp *http.Response, recv chan Message, done chan struct{}) {
			defer close(done)
			reader := bufio.NewReader(resp.Body)
			for {
				message, err := reader.ReadBytes('\n')

				if err != nil {
					log.Println(err)
					return
				}

				recv <- parseMessage(message, i)
			}
		}(resp, recv, done)

	L:
		for {
			select {
			case <-quit:
				retry = false
				select {
				case <-done:
				case <-time.After(time.Second):
				}
				return
			case <-done:
				// The recv goroutine errored. break the for and retry it
				log.Println("recv goroutine exited!")
				break L
			}
		}
	}
}

func parseMessage(data []byte, i int) Message {
	message := Message{Length: len(data), I: i}

	var result map[string]interface{}
	json.Unmarshal(data, &result)
	if _, ok := result["to_change_id"]; ok {
		message.ChangeId = int(result["to_change_id"].(float64))
	} else {
		log.Println(result)
		message.ChangeId = -1
	}

	return message
}

type Message struct {
	Length   int
	ChangeId int
	I        int
}

func getSessionId(user, pw, host string) http.CookieJar {
	values := map[string]string{"username": user, "password": pw}
	payload, _ := json.Marshal(values)
	loginUrl := "https://" + host + "/apps/users/login/"

	var client *http.Client
	tr := &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
	}
	client = &http.Client{Transport: tr}

	response, err := client.Post(loginUrl, "application/json", bytes.NewBuffer(payload))
	if err != nil {
		log.Fatal(err)
	}
	if response.StatusCode != 200 {
		log.Fatal(response.Status)
	}

	// Ok. get the session id
	var jar http.CookieJar
	cookieUrl := url.URL{Scheme: "https", Host: host, Path: "/"}
	jar, _ = cookiejar.New(nil)
	jar.SetCookies(&cookieUrl, response.Cookies())
	return jar
}

func getN() int {
	var N int
	if len(os.Args) <= 1 {
		N = 100
		log.Printf("Using %d connections (default!)\n", N)
	} else if len(os.Args) == 2 {
		var err interface{}
		N, err = strconv.Atoi(os.Args[1])
		if err != nil {
			log.Fatal(err)
		}
		log.Printf("Using %d connections\n", N)
	} else {
		log.Fatal("Too many arguments")
	}
	log.Println(N)
	return N
}

// host, user, pw
func getParams() (string, string, string) {
	file, err := os.Open("secrets")
	if err != nil {
		log.Fatal(err)
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	var fileTextLines []string
	for scanner.Scan() {
		fileTextLines = append(fileTextLines, scanner.Text())
	}
	if err := scanner.Err(); err != nil {
		log.Fatal(err)
	}

	if len(fileTextLines) != 3 {
		log.Fatal("The file `secrets` must contain three lines: host user password")
	}
	return fileTextLines[0], fileTextLines[1], fileTextLines[2]
}
